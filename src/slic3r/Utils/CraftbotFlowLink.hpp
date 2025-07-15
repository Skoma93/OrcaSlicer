#ifndef slic3r_CraftbotFlowLink_hpp_
#define slic3r_CraftbotFlowLink_hpp_

#include <string>
#include <wx/string.h>
#include <boost/optional.hpp>
#include <boost/asio/ip/address.hpp>

#include "PrintHost.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "OctoPrint.hpp"
#include "WebSocketClient.hpp"
namespace Slic3r {

class CraftbotFlowLink : public PrintHost
{
public:
    explicit CraftbotFlowLink(DynamicPrintConfig* config);
    ~CraftbotFlowLink() override = default;

    const char*                get_name() const override;
    bool                       test(wxString& curl_msg) const override;
    wxString                   get_test_ok_msg() const override;
    wxString                   get_test_failed_msg(wxString& msg) const override;
    bool                       upload(PrintHostUpload upload_data, ProgressFn prorgess_fn, ErrorFn error_fn, InfoFn info_fn) const override;
    bool                       has_auto_discovery() const override { return false; }
    bool                       can_test() const override { return true; }
    PrintHostPostUploadActions get_post_upload_actions() const override { return PrintHostPostUploadAction::StartPrint; }
    std::string                get_host() const override;
    std::string                make_url(const std::string& path) const;

protected:
    virtual void set_auth(Http& http) const;

private:
    std::string m_host;
    std::string m_username;
    std::string m_password;
    bool        start_print(wxString& msg, const std::string& filename) const;
    bool        send_file(const PrintHostUpload& upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const;
    std::string calc_sha256(const std::string& str) const;
    std::string base64_encode(const std::string& input) const;
};

} // namespace Slic3r

#endif