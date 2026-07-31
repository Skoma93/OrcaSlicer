#include "CraftbotPlusLink.hpp"

#include <chrono>
#include <algorithm>
#include <array>
#include <fstream>
#include <future>
#include <memory>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include <boost/algorithm/string.hpp>
#include <boost/asio.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/format.hpp>

#include "Http.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "slic3r/GUI/I18N.hpp"

namespace Slic3r {

namespace {

using boost::asio::ip::tcp;

constexpr auto   kConnectTimeout  = std::chrono::milliseconds(5000);
constexpr auto   kCommandTimeout  = std::chrono::milliseconds(2000);
constexpr auto   kTransferTimeout = std::chrono::milliseconds(50000);
constexpr auto   kHeaderPause     = std::chrono::milliseconds(200);
constexpr auto   kChunkPause      = std::chrono::microseconds(15);
constexpr size_t kChunkSize       = 1024;
constexpr unsigned short kDiscoveryPort = 80;
constexpr char kDiscoveryMessage[] = "#CRAFTBOT?\n";

wxString to_wx_string(const std::string& value) { return wxString::FromUTF8(value.c_str()); }

std::vector<std::string> craftbot_broadcast_addresses()
{
    std::set<std::string> addresses {"255.255.255.255", "192.168.0.255", "192.168.1.255"};
    boost::system::error_code ec;
    boost::asio::io_context io;
    boost::asio::ip::tcp::resolver resolver(io);
    const auto host_name = boost::asio::ip::host_name(ec);
    if (!ec) {
        const auto results = resolver.resolve(boost::asio::ip::tcp::v4(), host_name, "", ec);
        if (!ec) for (const auto& entry : results) {
            const auto address = entry.endpoint().address();
            if (!address.is_v4() || address.is_loopback()) continue;
            const auto bytes = address.to_v4().to_bytes();
            addresses.insert((boost::format("%1%.%2%.%3%.255") % int(bytes[0]) % int(bytes[1]) % int(bytes[2])).str());
        }
    }
    return {addresses.begin(), addresses.end()};
}

std::vector<std::string> flow_candidate_addresses()
{
    std::set<std::string> addresses;
    boost::system::error_code ec;
    boost::asio::io_context io;
    boost::asio::ip::tcp::resolver resolver(io);
    const auto host_name = boost::asio::ip::host_name(ec);
    if (!ec) {
        const auto results = resolver.resolve(boost::asio::ip::tcp::v4(), host_name, "", ec);
        if (!ec) for (const auto& entry : results) {
            const auto address = entry.endpoint().address();
            if (!address.is_v4() || address.is_loopback()) continue;
            const auto bytes = address.to_v4().to_bytes();
            for (int last = 1; last < 255; ++last) {
                if (last != bytes[3])
                    addresses.insert((boost::format("%1%.%2%.%3%.%4%") % int(bytes[0]) % int(bytes[1]) % int(bytes[2]) % last).str());
            }
        }
    }
    return {addresses.begin(), addresses.end()};
}

class CraftbotTcpSession
{
public:
    CraftbotTcpSession(const std::string& host, const std::string& port)
        : m_resolver(m_io_context), m_socket(m_io_context), m_host(host), m_port(port)
    {}

    ~CraftbotTcpSession() { close(); }

    bool connect(std::chrono::milliseconds timeout, std::string* error_message = nullptr)
    {
        close();
        m_recv_buffer.consume(m_recv_buffer.size());

        boost::system::error_code resolve_ec;
        auto                      endpoints = std::make_shared<tcp::resolver::results_type>(m_resolver.resolve(m_host, m_port, resolve_ec));

        if (resolve_ec) {
            if (error_message != nullptr)
                *error_message = resolve_ec.message();
            return false;
        }

        boost::system::error_code op_ec;
        bool                      finished = false;

        m_io_context.restart();
        boost::asio::async_connect(m_socket, *endpoints, [&, endpoints](const boost::system::error_code& ec, const tcp::endpoint&) {
            op_ec    = ec;
            finished = true;
        });

        if (!pump_until_finished(timeout, finished)) {
            if (error_message != nullptr)
                *error_message = "Connection timed out";
            close();
            return false;
        }

        if (op_ec) {
            if (error_message != nullptr)
                *error_message = op_ec.message();
            close();
            return false;
        }

        boost::system::error_code option_ec;
        m_socket.set_option(tcp::no_delay(true), option_ec);

        return true;
    }

    bool send_command(const std::string& command, std::chrono::milliseconds timeout, std::string* error_message = nullptr)
    {
        std::string payload = command;
        if (payload.empty() || payload.back() != '\n')
            payload.push_back('\n');

        return send_raw(payload, timeout, error_message);
    }

    bool send_raw(const std::string& payload, std::chrono::milliseconds timeout, std::string* error_message = nullptr)
    {
        return send_raw(payload.data(), payload.size(), timeout, error_message);
    }

    bool send_raw(const char* data, size_t size, std::chrono::milliseconds timeout, std::string* error_message = nullptr)
    {
        boost::system::error_code op_ec;
        std::size_t               bytes_written = 0;
        bool                      finished      = false;

        m_io_context.restart();
        boost::asio::async_write(m_socket, boost::asio::buffer(data, size),
                                 [&](const boost::system::error_code& ec, std::size_t transferred) {
                                     op_ec         = ec;
                                     bytes_written = transferred;
                                     finished      = true;
                                 });

        if (!pump_until_finished(timeout, finished)) {
            if (error_message != nullptr)
                *error_message = "Write timed out";
            close();
            return false;
        }

        if (op_ec) {
            if (error_message != nullptr)
                *error_message = op_ec.message();
            close();
            return false;
        }

        if (bytes_written != size) {
            if (error_message != nullptr)
                *error_message = "Incomplete write";
            close();
            return false;
        }

        return true;
    }

    bool read_line(std::string& line, std::chrono::milliseconds timeout, std::string* error_message = nullptr)
    {
        boost::system::error_code op_ec;
        bool                      finished = false;

        m_io_context.restart();
        boost::asio::async_read_until(m_socket, m_recv_buffer, '\n', [&](const boost::system::error_code& ec, std::size_t) {
            op_ec    = ec;
            finished = true;
        });

        if (!pump_until_finished(timeout, finished)) {
            if (error_message != nullptr)
                *error_message = "Read timed out";
            close();
            return false;
        }

        if (op_ec) {
            if (error_message != nullptr)
                *error_message = op_ec.message();
            close();
            return false;
        }

        std::istream input(&m_recv_buffer);
        std::getline(input, line);
        boost::trim(line);
        return true;
    }

    bool read_until(const std::string& marker, std::chrono::milliseconds timeout)
    {
        boost::system::error_code op_ec;
        bool finished = false;
        m_io_context.restart();
        boost::asio::async_read_until(m_socket, m_recv_buffer, marker,
                                      [&](const boost::system::error_code& ec, std::size_t) { op_ec = ec; finished = true; });
        return pump_until_finished(timeout, finished) && !op_ec;
    }

    bool send_command_and_read_line(const std::string&        command,
                                    std::chrono::milliseconds write_timeout,
                                    std::chrono::milliseconds read_timeout,
                                    std::string&              line,
                                    std::string*              error_message = nullptr)
    {
        if (!send_command(command, write_timeout, error_message))
            return false;

        return read_line(line, read_timeout, error_message);
    }

    void close()
    {
        boost::system::error_code ec;
        if (m_socket.is_open()) {
            m_socket.shutdown(tcp::socket::shutdown_both, ec);
            m_socket.close(ec);
        }
    }

private:
    bool pump_until_finished(std::chrono::milliseconds timeout, bool& finished)
    {
        const auto deadline = std::chrono::steady_clock::now() + timeout;

        while (!finished) {
            if (std::chrono::steady_clock::now() >= deadline)
                return false;

            m_io_context.run_for(std::chrono::milliseconds(10));

            if (!finished && m_io_context.stopped())
                m_io_context.restart();
        }

        return true;
    }

    boost::asio::io_context m_io_context;
    tcp::resolver           m_resolver;
    tcp::socket             m_socket;
    boost::asio::streambuf  m_recv_buffer;
    std::string             m_host;
    std::string             m_port;
};

bool is_flow_admin(const std::string& address)
{
    CraftbotTcpSession session(address, "80");
    if (!session.connect(std::chrono::milliseconds(400)))
        return false;
    const std::string request = "GET /login HTTP/1.1\r\nHost: " + address + "\r\nConnection: close\r\n\r\n";
    return session.send_raw(request, std::chrono::milliseconds(400)) &&
           session.read_until("<title>CraftBot Flow Admin</title>", std::chrono::milliseconds(800));
}

} // namespace

CraftbotPlusLink::CraftbotPlusLink(DynamicPrintConfig* config)
{
    if (config) {
        m_host = config->opt_string("print_host");
        m_port = "80";
    }
}

bool CraftbotPlusLink::parse_discovery_response(const char* data, size_t size, const std::string& ip_address,
                                                CraftbotDiscoveredPrinter& printer)
{
    std::string response(data, size);
    boost::trim(response);
    if (!boost::starts_with(response, "CB_CraftBot") || response.size() == 11 ||
        !std::all_of(response.begin(), response.end(), [](unsigned char ch) { return ch >= 0x20 && ch <= 0x7e; }))
        return false;
    printer = {response.substr(3), ip_address};
    return true;
}

bool CraftbotPlusLink::discover_printers(std::vector<CraftbotDiscoveredPrinter>& printers, wxString& msg,
                                         int timeout_ms, int idle_timeout_ms, int max_retries)
{
    printers.clear();
    try {
        std::map<std::string, CraftbotDiscoveredPrinter> found;
        boost::asio::io_context io;
        boost::asio::ip::udp::socket socket(io);
        boost::system::error_code ec;
        socket.open(boost::asio::ip::udp::v4(), ec);
        if (!ec) socket.set_option(boost::asio::socket_base::broadcast(true), ec);
        if (!ec) socket.bind({boost::asio::ip::udp::v4(), 0}, ec);
        if (!ec) socket.non_blocking(true, ec);
        if (ec) { msg = to_wx_string(ec.message()); return false; }

        const auto addresses = craftbot_broadcast_addresses();
        for (int attempt = 0; attempt < std::max(1, max_retries); ++attempt) {
            for (const auto& address : addresses) {
                const auto destination = boost::asio::ip::make_address_v4(address, ec);
                if (ec) { ec.clear(); continue; }
                socket.send_to(boost::asio::buffer(kDiscoveryMessage, sizeof(kDiscoveryMessage) - 1),
                               {destination, kDiscoveryPort}, 0, ec);
                ec.clear();
            }
            const auto start = std::chrono::steady_clock::now();
            auto last_reply = start;
            while (std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count() < timeout_ms) {
                if (!found.empty() && std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - last_reply).count() >= idle_timeout_ms)
                    break;
                std::array<char, 256> buffer;
                boost::asio::ip::udp::endpoint remote;
                const size_t received = socket.receive_from(boost::asio::buffer(buffer), remote, 0, ec);
                if (!ec) {
                    CraftbotDiscoveredPrinter printer;
                    if (remote.port() == kDiscoveryPort && parse_discovery_response(buffer.data(), received, remote.address().to_string(), printer)) {
                        found[printer.ip_address] = std::move(printer);
                        last_reply = std::chrono::steady_clock::now();
                    }
                } else if (ec == boost::asio::error::would_block || ec == boost::asio::error::try_again) {
                    ec.clear();
                    std::this_thread::sleep_for(std::chrono::milliseconds(50));
                } else { msg = to_wx_string(ec.message()); return false; }
            }
            if (!found.empty()) break;
        }
        for (auto& item : found)
            printers.emplace_back(std::move(item.second));
        std::sort(printers.begin(), printers.end(), [](const auto& lhs, const auto& rhs) {
            return lhs.name == rhs.name ? lhs.ip_address < rhs.ip_address : lhs.name < rhs.name;
        });
        if (printers.empty()) {
            msg = "No Craftbot printers were discovered on the local network.";
            return false;
        }
        return true;
    } catch (const std::exception& ex) {
        msg = to_wx_string(ex.what());
        return false;
    }
}

bool CraftbotPlusLink::discover_flow_printers(std::vector<CraftbotDiscoveredPrinter>& printers, wxString& msg)
{
    printers.clear();
    const auto candidates = flow_candidate_addresses();
    constexpr size_t batch_size = 32;
    for (size_t offset = 0; offset < candidates.size(); offset += batch_size) {
        std::vector<std::future<CraftbotDiscoveredPrinter>> probes;
        const size_t end = std::min(candidates.size(), offset + batch_size);
        for (size_t i = offset; i < end; ++i) {
            probes.emplace_back(std::async(std::launch::async, [address = candidates[i]] {
                try {
                    if (is_flow_admin(address))
                        return CraftbotDiscoveredPrinter{"CraftBot Flow", address};
                } catch (...) {}
                return CraftbotDiscoveredPrinter{};
            }));
        }
        for (auto& probe : probes) {
            auto printer = probe.get();
            if (!printer.ip_address.empty())
                printers.emplace_back(std::move(printer));
        }
        if (!printers.empty())
            break;
    }
    if (printers.empty()) {
        msg = "No Craftbot Flow printers were discovered on the local network.";
        return false;
    }
    return true;
}

const char* CraftbotPlusLink::get_name() const { return "CraftbotPlus"; }

bool CraftbotPlusLink::test(wxString& msg) const
{
    CraftbotTcpSession session(m_host, m_port);
    std::string        error_message;

    if (!session.connect(kConnectTimeout, &error_message)) {
        msg = to_wx_string(error_message);
        return false;
    }

    std::string line;
    if (!session.send_command_and_read_line("#GETSTATE", kCommandTimeout, kCommandTimeout, line, &error_message)) {
        msg = to_wx_string(error_message);
        return false;
    }

    std::vector<std::string> tokens;
    boost::split(tokens, line, boost::is_any_of(","));

    if (tokens.size() < 7) {
        msg = "Unsupported device";
        return false;
    }

    if (tokens[6] != "1") {
        msg = "The pendrive is not being recognized by the device";
        return false;
    }

    return true;
}

wxString CraftbotPlusLink::get_test_failed_msg(wxString& msg) const
{
    return wxString::Format(_L("Could not reach Craftbot device: %s"), msg);
}

wxString CraftbotPlusLink::get_test_ok_msg() const { return _L("Craftbot device is reachable."); }

std::string CraftbotPlusLink::get_host() const { return m_host; }

bool CraftbotPlusLink::upload(PrintHostUpload upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const
{
    return send_file(upload_data, progress_fn, error_fn, info_fn);
}

bool CraftbotPlusLink::send_file(const PrintHostUpload& upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const
{
    (void) info_fn;

    wxString test_msg;
    if (!test(test_msg)) {
        error_fn(test_msg);
        return false;
    }

    std::ifstream file(upload_data.source_path.c_str(), std::ios::binary);
    if (!file.is_open()) {
        error_fn("Failed to open file.");
        return false;
    }

    file.seekg(0, std::ios::end);
    const size_t file_size = static_cast<size_t>(file.tellg());
    file.seekg(0, std::ios::beg);

    CraftbotTcpSession session(m_host, m_port);
    std::string        error_message;

    if (!session.connect(kConnectTimeout, &error_message)) {
        error_fn(to_wx_string(error_message));
        return false;
    }

    const std::string header = "#UFILE&" + upload_data.upload_path.filename().string() + "," + std::to_string(file_size);

    if (!session.send_command(header, kTransferTimeout, &error_message)) {
        error_fn(to_wx_string(error_message));
        return false;
    }

    std::this_thread::sleep_for(kHeaderPause);

    size_t            total_sent = 0;
    bool              cancel     = false;
    auto              start_time = std::chrono::steady_clock::now();
    std::string       last_chunk;
    std::vector<char> buffer(kChunkSize);

    while (file && !cancel) {
        file.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        const std::streamsize bytes_read = file.gcount();

        if (bytes_read <= 0)
            break;

        if (!session.send_raw(buffer.data(), static_cast<size_t>(bytes_read), kTransferTimeout, &error_message)) {
            error_fn(to_wx_string(error_message));
            return false;
        }

        std::this_thread::sleep_for(kChunkPause);

        last_chunk.assign(buffer.data(), static_cast<size_t>(bytes_read));
        total_sent += static_cast<size_t>(bytes_read);

        const auto   now         = std::chrono::steady_clock::now();
        const double elapsed_sec = std::chrono::duration<double>(now - start_time).count();
        const double speed       = elapsed_sec > 0.0 ? static_cast<double>(total_sent) / elapsed_sec : 0.0;

        Http::Progress progress(0, 0, file_size, total_sent, last_chunk, speed);
        progress_fn(std::move(progress), cancel);
    }

    if (cancel)
        return false;

    if (upload_data.post_action == PrintHostPostUploadAction::StartPrint) {
        const std::string start_file_command = "#UPRINT&" + upload_data.upload_path.filename().stem().string();

        if (!session.send_command(start_file_command, kTransferTimeout, &error_message)) {
            error_fn(to_wx_string(error_message));
            return false;
        }
    }

    return true;
}

bool CraftbotPlusLink::start_print(wxString& msg, const std::string& filename) const
{
    CraftbotTcpSession session(m_host, m_port);
    std::string        error_message;

    if (!session.connect(kConnectTimeout, &error_message)) {
        msg = to_wx_string(error_message);
        return false;
    }

    if (!session.send_command("#UPRINT&" + filename, kCommandTimeout, &error_message)) {
        msg = to_wx_string(error_message);
        return false;
    }

    return true;
}

} // namespace Slic3r
