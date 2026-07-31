#ifndef slic3r_CraftbotPlusLink_hpp_
#define slic3r_CraftbotPlusLink_hpp_

#include <cstddef>
#include <string>
#include <vector>
#include <wx/string.h>
#include <boost/optional.hpp>
#include <boost/asio/ip/address.hpp>

#include "PrintHost.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "OctoPrint.hpp"
#include "WebSocketClient.hpp"

namespace Slic3r {

struct CraftbotDiscoveredPrinter
{
    std::string name;
    std::string ip_address;
};

class CraftbotPlusLink : public PrintHost
{
public:
    explicit CraftbotPlusLink(DynamicPrintConfig* config);
    ~CraftbotPlusLink() override = default;

    const char*                get_name() const override;
    bool                       can_test() const override { return true; }
    std::string                get_host() const override;
    bool                       has_auto_discovery() const override { return true; }
    static bool                discover_printers(std::vector<CraftbotDiscoveredPrinter>& printers, wxString& msg,
                                                 int timeout_ms = 5000, int idle_timeout_ms = 1000, int max_retries = 3);
    static bool                discover_flow_printers(std::vector<CraftbotDiscoveredPrinter>& printers, wxString& msg);
    static bool                parse_discovery_response(const char* data, size_t size, const std::string& ip_address,
                                                        CraftbotDiscoveredPrinter& printer);

    wxString                   get_test_ok_msg() const override;
    wxString                   get_test_failed_msg(wxString& msg) const override;
    bool                       test(wxString& curl_msg) const override;
    PrintHostPostUploadActions get_post_upload_actions() const override { return PrintHostPostUploadAction::StartPrint; }

    bool                       upload(PrintHostUpload upload_data, ProgressFn prorgess_fn, ErrorFn error_fn, InfoFn info_fn) const override;

private:
    std::string m_host;
    std::string m_port;
    bool        start_print(wxString& msg, const std::string& filename) const;
    bool        send_file(const PrintHostUpload& upload_data, ProgressFn progress_fn, ErrorFn error_fn, InfoFn info_fn) const;
};

} // namespace Slic3r

#endif



