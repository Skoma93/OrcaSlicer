#include "CraftbotPlusLink.hpp"
#include <algorithm>
#include <ctime>
#include <chrono>
#include <thread>
#include <boost/filesystem/path.hpp>
#include <boost/format.hpp>
#include <boost/log/trivial.hpp>
#include <boost/property_tree/ptree.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/asio.hpp>
#include <boost/algorithm/string.hpp>
#include "TCPConsole.hpp"

#include <wx/frame.h>
#include <wx/event.h>
#include <wx/progdlg.h>
#include <wx/sizer.h>
#include <wx/stattext.h>
#include <wx/textctrl.h>
#include <wx/checkbox.h>

#include "libslic3r/PrintConfig.hpp"
#include "slic3r/GUI/GUI.hpp"
#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/MsgDialog.hpp"
#include "Http.hpp"
#include "SerialMessage.hpp"
#include "SerialMessageType.hpp"

namespace Slic3r {

CraftbotPlusLink::CraftbotPlusLink(DynamicPrintConfig* config)
{

    if (config) {
        m_host     = config->opt_string("print_host");
        m_port = "80";
    }
}

const char* CraftbotPlusLink::get_name() const { return "CraftbotPlus"; }

bool CraftbotPlusLink::test(wxString& msg) const
{
    Slic3r::Utils::TCPConsole console;
    console.set_remote(m_host, m_port);
    console.set_line_delimiter("\n");
    console.set_command_done_string(""); 
    console.set_done_str_in_msg(true);
    console.set_write_timeout(std::chrono::milliseconds(2000));
    console.set_read_timeout(std::chrono::milliseconds(2000));

    std::string line;
    bool valid = console.send_and_receive("#GETSTATE", line);

    if (!valid) {
        msg = wxString::FromUTF8(console.error_message().c_str());
        return false;
    }
        
    std::vector<std::string> tokens;
    boost::split(tokens, line, boost::is_any_of(","));

    if (tokens.size() < 4) {
        
        msg = "Unsupported device";
        return false;
    } 


    if (tokens[6] != "1") {
        msg = "The pendrive is not being recognized by the device";
        return false;
    }
    

    return true;
}

wxString CraftbotPlusLink::get_test_failed_msg(wxString& msg) const { return wxString::Format(_L("Could not reach Craftbot device: %s"), msg); }

wxString CraftbotPlusLink::get_test_ok_msg() const { return _L("Craftbot device is reachable."); }

std::string CraftbotPlusLink::get_host() const { return m_host; }

bool CraftbotPlusLink::upload(PrintHostUpload upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const
{
    return send_file(upload_data, progress_fn, error_fn, info_fn);
}
bool CraftbotPlusLink::send_file(const PrintHostUpload& upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const
{
    // Test before send
    wxString test_msg;
    if (!test(test_msg)) {
        error_fn(test_msg);
        return false;
    }



    Slic3r::Utils::TCPConsole console;
    console.set_remote(m_host, m_port);
    console.set_line_delimiter("\r\n");
    console.set_command_done_string("");
    console.set_done_str_in_msg(true);
    console.set_write_timeout(std::chrono::milliseconds(2000));
    console.set_read_timeout(std::chrono::milliseconds(2000));

    std::ifstream newfile(upload_data.source_path.c_str(), std::ios::binary);
    if (!newfile.is_open()) {
        error_fn("Failed to open file.");
        return false;
    }

    newfile.seekg(0, std::ios::end);
    size_t file_size = newfile.tellg();
    newfile.seekg(0, std::ios::beg);

    bool queue_started = false;

    console.enqueue_cmd(Slic3r::Utils::SerialMessage("#UBLOCK&" + std::to_string(file_size), Slic3r::Utils::Command));

    if (!queue_started) {
        console.run_queue();
    }
}

bool CraftbotPlusLink::start_print(wxString& msg, const std::string& filename) const
{
    bool success = true;

   

    return success;
}

} // namespace Slic3r