#ifndef slic3r_CraftbotPlusLink_hpp_
#define slic3r_CraftbotPlusLink_hpp_

#include <string>
#include <wx/string.h>
#include <boost/optional.hpp>
#include <boost/asio/ip/address.hpp>

#include "PrintHost.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "OctoPrint.hpp"
#include "WebSocketClient.hpp"
namespace Slic3r {

class CraftbotPlusLink : public PrintHost
{
public:
    explicit CraftbotPlusLink(DynamicPrintConfig* config);
    ~CraftbotPlusLink() override = default;

    const char*                get_name() const override;
    bool                       test(wxString& curl_msg) const override;
    wxString                   get_test_ok_msg() const override;
    wxString                   get_test_failed_msg(wxString& msg) const override;
    bool                       upload(PrintHostUpload upload_data, ProgressFn prorgess_fn, ErrorFn error_fn, InfoFn info_fn) const override;
    bool                       has_auto_discovery() const override { return false; }
    bool                       can_test() const override { return true; }
    PrintHostPostUploadActions get_post_upload_actions() const override { return PrintHostPostUploadAction::StartPrint; }
    std::string                get_host() const override;


private:
    std::string m_host;
    std::string m_port;
    bool        start_print(wxString& msg, const std::string& filename) const;
    bool        send_file(const PrintHostUpload& upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const;
};

} // namespace Slic3r

#endif