#include "CraftbotFlowLink.hpp"
#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>

#include <openssl/sha.h>
#include <wx/string.h>
#include <boost/format.hpp>
#include <boost/log/trivial.hpp>

#include "slic3r/GUI/I18N.hpp"
#include "Http.hpp"
#include "libslic3r/AppConfig.hpp"

namespace Slic3r {

CraftbotFlowLink::CraftbotFlowLink(DynamicPrintConfig* config)
{
    // You can read these from config if needed
    if (config) {
        m_host     = config->opt_string("print_host");         //"10.0.1.91";
        m_username = config->opt_string("printhost_user");     //"craft";
        m_password = config->opt_string("printhost_password"); //"craftunique";
    }
}

const char* CraftbotFlowLink::get_name() const { return "Craftbot"; }

bool CraftbotFlowLink::test(wxString& curl_msg) const
{
    bool success = true;
    auto url     = make_url("remoteupload");

    BOOST_LOG_TRIVIAL(info) << boost::format("%1%: Testing connection to %2%") % get_name() % url;

    auto http = Http::get(url);
    set_auth(http);

    http.on_error([&](std::string body, std::string error, unsigned status) {
        curl_msg = format_error(body, error, status);
        success  = false;
    });

    http.on_complete([&](std::string body, unsigned status) {
        BOOST_LOG_TRIVIAL(debug) << boost::format("%1%: GET %2% succeeded. Status: %3%") % get_name() % url % status;
    });

    http.perform_sync();
    return success;
}

wxString CraftbotFlowLink::get_test_failed_msg(wxString& msg) const
{
    return wxString::Format(_L("Could not reach Craftbot device: %s"), msg);
}

wxString CraftbotFlowLink::get_test_ok_msg() const { return _L("Craftbot device is reachable."); }

std::string CraftbotFlowLink::get_host() const { return m_host; }

bool CraftbotFlowLink::upload(PrintHostUpload upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const
{
    return send_file(upload_data, progress_fn, error_fn, info_fn);
}
bool CraftbotFlowLink::send_file(const PrintHostUpload& upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const
{
    std::string pwd_sha   = calc_sha256("flow_admin_" + m_password);
    std::string final_sha = calc_sha256("-" + m_username + "-" + pwd_sha + "-");
    std::string auth      = base64_encode(m_username + ":" + final_sha);

    // Load file contents
    std::ifstream file(upload_data.source_path.string(), std::ios::binary);
    if (!file) {
        error_fn("Failed to open file: " + upload_data.source_path.string());
        return false;
    }
    std::vector<char> data((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());

    BOOST_LOG_TRIVIAL(info) << "Craftbot: Read " << data.size() << " bytes for upload.";

    Http::set_extra_headers({{"User-Agent", "CraftWare"}});

    const std::string url  = "http://" + m_host + "/remoteupload";
    auto              http = Http::post(url);

    http.remove_header("Accept");

    http.header("Content-Type", "application/octet-stream");
    http.header("Content-Length", std::to_string(data.size()));
    http.header("Name", upload_data.upload_path.filename().string());
    http.header("Authorization", "Basic " + auth);
    http.header("Host", m_host);
    http.header("Cache-Control", "no-cache");

    // Set POST body
    http.set_post_body(std::string(data.data(), data.size()));

    bool success = true;

    http.on_progress([&](Http::Progress progress, bool& cancel) {
        progress_fn(std::move(progress), cancel);
        if (cancel) {
            success = false;
            BOOST_LOG_TRIVIAL(info) << "Craftbot: Upload canceled by user.";
        }
    });

    http.on_error([&](std::string body, std::string error, unsigned status) {
        BOOST_LOG_TRIVIAL(error) << "Craftbot: Upload failed. HTTP " << status << ", error: " << error << ", body: " << body;
        error_fn(format_error(body, error, status));
        success = false;
    });

    http.on_complete([&](std::string body, unsigned status) {
        BOOST_LOG_TRIVIAL(info) << "Craftbot: Upload complete. HTTP " << status;
        info_fn("craftbot", _L("Upload successful"));
    });

    http.perform_sync();

    if (success && upload_data.post_action == PrintHostPostUploadAction::StartPrint) {
        wxString errormsg;
        success = start_print(errormsg, upload_data.upload_path.string());
        if (!success) {
            error_fn(std::move(errormsg));
        }
    }
    return success;
}

bool CraftbotFlowLink::start_print(wxString& msg, const std::string& filename) const
{
    std::string pwd_sha   = calc_sha256("flow_admin_" + m_password);
    std::string final_sha = calc_sha256("-" + m_username + "-" + pwd_sha + "-");
    std::string auth      = base64_encode(m_username + ":" + final_sha);

    Http::set_extra_headers({{"User-Agent", "CraftWare"}});

    const std::string url  = "http://" + m_host + "/remotestartprint";
    auto              http = Http::post(url);

    http.remove_header("Accept");

    http.header("Content-Type", "application/json");
    http.header("Authorization", "Basic " + auth);
    http.header("Host", m_host);
    http.header("Cache-Control", "no-cache");

    // JSON body with filename
    std::ostringstream json;
    json << "{ \"fileName\": \"" << filename << "\" }";
    http.set_post_body(json.str());

    bool success = true;

    http.on_error([&](std::string body, std::string error, unsigned status) {
        BOOST_LOG_TRIVIAL(error) << "Craftbot: Start print failed. HTTP " << status << ", error: " << error << ", body: " << body;
        msg     = wxString::Format("Craftbot: Failed to start print. HTTP %u - %s", status, error);
        success = false;
    });

    http.on_complete([&](std::string body, unsigned status) {
        BOOST_LOG_TRIVIAL(info) << "Craftbot: Start print succeeded. HTTP " << status;
        msg = "Craftbot: Print started successfully.";
    });

    http.perform_sync();

    return success;
}

std::string CraftbotFlowLink::calc_sha256(const std::string& input) const
{
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(input.c_str()), input.size(), hash);

    std::ostringstream oss;
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i)
        oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(hash[i]);
    return oss.str();
}

std::string CraftbotFlowLink::base64_encode(const std::string& input) const
{
    static constexpr char table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string           output;
    int                   val = 0, valb = -6;
    for (uint8_t c : input) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            output.push_back(table[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6)
        output.push_back(table[((val << 8) >> (valb + 8)) & 0x3F]);
    while (output.size() % 4)
        output.push_back('=');
    return output;
}

void CraftbotFlowLink::set_auth(Http& http) const
{
    std::string pwd_sha   = calc_sha256("flow_admin_" + m_password);
    std::string final_sha = calc_sha256("-" + m_username + "-" + pwd_sha + "-");
    std::string auth      = base64_encode(m_username + ":" + final_sha);
    http.header("Authorization", "Basic " + auth);
}

std::string CraftbotFlowLink::make_url(const std::string& path) const
{
    if (m_host.find("http://") == 0 || m_host.find("https://") == 0)
        return m_host.back() == '/' ? m_host + path : m_host + "/" + path;
    else
        return "http://" + m_host + "/" + path;
}

} // namespace Slic3r