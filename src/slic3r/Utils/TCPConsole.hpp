#ifndef slic3r_Utils_TCPConsole_hpp_
#define slic3r_Utils_TCPConsole_hpp_

#include <string>
#include <deque>
#include <boost/system/error_code.hpp>
#include <boost/system/system_error.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/streambuf.hpp>
#include "SerialMessage.hpp"

namespace Slic3r {
namespace Utils {

using boost::asio::ip::tcp;

// Generic command / response TCP telnet like console class.
// Used by the MKS host to send G-code commands to test connection ("M105") and to start printing ("M23 filename", "M24").
class TCPConsole
{
public:
    TCPConsole() : m_resolver(m_io_context), m_socket(m_io_context) { set_defaults(); }
    TCPConsole(const std::string& host_name, const std::string& port_name) : m_resolver(m_io_context), m_socket(m_io_context)
        { set_defaults(); set_remote(host_name, port_name); }
    ~TCPConsole() = default;

    void set_defaults()
    {
        m_newline = "\n";
        m_done_string = "ok";
        m_connect_timeout = std::chrono::milliseconds(5000);
        m_write_timeout = std::chrono::milliseconds(10000);
        m_read_timeout = std::chrono::milliseconds(10000);
        m_tcp_queue_delay = std::chrono::milliseconds(0);
        m_is_done_string_in_msg = false;
        m_auto_close_socket     = true;
        m_is_connected          = false;
        m_ack_wait              = false;
    }

    void set_done_str_in_msg(bool val) {
        m_is_done_string_in_msg=val;
    }

    void set_write_timeout(std::chrono::steady_clock::duration timeout) {
        m_write_timeout = timeout;
    }

    void set_read_timeout(std::chrono::steady_clock::duration timeout) {
        m_read_timeout = timeout;
    }

    void set_tcp_queue_delay(std::chrono::steady_clock::duration delay) { 
        m_tcp_queue_delay = delay;
    }

    void set_line_delimiter(const std::string& newline) {
        m_newline = newline;
    }
    void set_command_done_string(const std::string& done_string) {
        m_done_string = done_string;
    }

    void set_remote(const std::string& host_name, const std::string& port_name)
    {
        m_host_name = host_name;
        m_port_name = port_name;
    }

    void set_auto_close_socket(bool newVal)
    { 
        m_auto_close_socket = newVal;
    }

    bool enqueue_cmd(const SerialMessage& cmd) {
        // TODO: Add multithread protection to queue
        m_cmd_queue.push_back(cmd);
        return true;
    }

    size_t get_cmd_queue_size() const {
        return static_cast<int>(m_cmd_queue.size()); 
    }
    void   set_ack_wait(bool val)
    { 
        m_ack_wait = val;
    }


    bool run_queue();
    
    std::string error_message() const { return m_error_code.message(); }
    bool        send_and_receive(SerialMessage message, std::string& recv_msg);
    void disconnect()
    {
        if (m_is_connected) {
            m_socket.close();
            m_is_connected = false;
        }
    }

private:
    void handle_connect(const boost::system::error_code& ec);
    void handle_read(const boost::system::error_code& ec, std::size_t bytes_transferred);
    void handle_write(const boost::system::error_code& ec, std::size_t bytes_transferred, SerialMessageType messageType);

    void transmit_next_command();
    void wait_next_line();
    void handle_tcp_ack(const boost::system::error_code& ec, std::size_t bytes_transferred);
    void wait_for_ack();
    std::string extract_next_line();

    void set_deadline_in(std::chrono::steady_clock::duration);
    bool is_deadline_over() const;

    std::string                             m_host_name;
    std::string                             m_port_name;
    std::string                             m_newline;
    std::string                             m_done_string;
    bool                                    m_is_done_string_in_msg;
    std::chrono::steady_clock::duration     m_connect_timeout;
    std::chrono::steady_clock::duration     m_write_timeout;
    std::chrono::steady_clock::duration     m_read_timeout;
    std::chrono::steady_clock::duration     m_tcp_queue_delay;

    std::deque<SerialMessage>                 m_cmd_queue;

    boost::asio::io_context                 m_io_context;
    tcp::resolver                           m_resolver;
    tcp::socket                             m_socket;
    boost::asio::streambuf                  m_recv_buffer;
    std::string                             m_send_buffer;

    bool                                    m_is_connected;
    bool                                    m_ack_wait;
    bool                                    m_auto_close_socket;
    boost::system::error_code               m_error_code;
    std::chrono::steady_clock::time_point   m_deadline;
    std::string*                            m_last_msg_ptr = nullptr;

};

} // Utils
} // Slic3r

#endif
