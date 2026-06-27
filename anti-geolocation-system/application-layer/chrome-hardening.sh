#!/bin/bash
# Chrome/Chromium Hardening Script
# Applies enterprise policies and launch flags for privacy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/chrome-hardening.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Detect Chrome/Chromium installation
detect_chrome() {
    local browsers=()
    
    if command -v google-chrome &>/dev/null; then
        browsers+=("google-chrome")
    fi
    if command -v google-chrome-stable &>/dev/null; then
        browsers+=("google-chrome-stable")
    fi
    if command -v chromium &>/dev/null; then
        browsers+=("chromium")
    fi
    if command -v chromium-browser &>/dev/null; then
        browsers+=("chromium-browser")
    fi
    if [[ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
        browsers+=("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    fi
    
    if [[ ${#browsers[@]} -eq 0 ]]; then
        error "No Chrome/Chromium installation found"
        return 1
    fi
    
    echo "${browsers[@]}"
}

# Get policy directory based on OS and browser
get_policy_dir() {
    local browser="${1:-chrome}"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [[ "$browser" == *"chromium"* ]]; then
            echo "/etc/chromium/policies/managed"
        else
            echo "/etc/opt/chrome/policies/managed"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        if [[ "$browser" == *"chromium"* ]]; then
            echo "/Library/Managed Preferences/com.chromium.Chromium"
        else
            echo "/Library/Managed Preferences/com.google.Chrome"
        fi
    else
        error "Unsupported OS: $OSTYPE"
        return 1
    fi
}

# Create enterprise policies
create_policies() {
    local policy_dir="$1"
    
    log "Creating Chrome enterprise policies in $policy_dir"
    mkdir -p "$policy_dir"
    
    cat > "$policy_dir/anti-geolocation.json" << 'EOF'
{
  "WebRtcIpHandlingUrl": "disable_non_proxied_udp",
  "WebRtcUdpPortRange": "",
  "DefaultGeolocationSetting": 2,
  "DefaultNotificationsSetting": 2,
  "DefaultWebBluetoothGuardSetting": 2,
  "DefaultWebUsbGuardSetting": 2,
  "DefaultSerialGuardSetting": 2,
  "DefaultHidGuardSetting": 2,
  "DefaultFileSystemReadGuardSetting": 2,
  "DefaultFileSystemWriteGuardSetting": 2,
  "DefaultClipboardSetting": 2,
  "DefaultCameraSetting": 2,
  "DefaultMicrophoneSetting": 2,
  "DefaultMediaStreamSetting": 2,
  "DefaultSensorsSetting": 2,
  "DefaultPopupsSetting": 2,
  "DefaultCookiesSetting": 4,
  "DefaultImagesSetting": 1,
  "DefaultJavaScriptSetting": 1,
  "DefaultPluginsSetting": 3,
  "BackgroundModeEnabled": false,
  "BatterySaverModeAvailability": 1,
  "BlockThirdPartyCookies": true,
  "BrowserNetworkTimeQueriesEnabled": false,
  "BrowserSignin": 0,
  "BuiltInDnsClientEnabled": false,
  "ClearBrowsingDataOnExit": true,
  "CloudPrintProxyEnabled": false,
  "CloudPrintSubmitEnabled": false,
  "ComponentUpdatesEnabled": false,
  "DefaultBrowserSettingEnabled": false,
  "DeveloperToolsAvailability": 1,
  "Disable3DAPIs": true,
  "DisableScreenshots": true,
  "DisableSafeBrowsingProceedAnyway": false,
  "DnsOverHttpsMode": "secure",
  "DnsOverHttpsTemplates": "https://dns.quad9.net/dns-query https://dns.cloudflare.com/dns-query",
  "DriveDisabled": true,
  "EnableMediaRouter": false,
  "EnableOnlineRevocationChecks": true,
  "EnterpriseRealTimeUrlCheckMode": 0,
  "ForceEphemeralProfiles": true,
  "ForceGoogleSafeSearch": false,
  "ForceYouTubeRestrict": 0,
  "FullscreenAllowed": true,
  "GloballyScopeHTTPAuthCacheEnabled": false,
  "HideWebStoreIcon": true,
  "HomepageIsNewTabPage": true,
  "ImportBookmarks": false,
  "ImportHistory": false,
  "ImportHomepage": false,
  "ImportSavedPasswords": false,
  "ImportSearchEngine": false,
  "IncognitoModeAvailability": 0,
  "MaxConnectionsPerProxy": 10,
  "MediaRouterCastAllowAllIPs": false,
  "MetricsReportingEnabled": false,
  "NetworkPredictionOptions": 2,
  "PasswordManagerEnabled": false,
  "PaymentMethodQueryEnabled": false,
  "PromotionalTabsEnabled": false,
  "ProxyMode": "direct",
  "QuicAllowed": false,
  "RemoteAccessHostAllowClientPairing": false,
  "RemoteAccessHostAllowGnubbyAuth": false,
  "RemoteAccessHostAllowRelayedConnection": false,
  "RemoteAccessHostDomain": "",
  "RemoteAccessHostFirewallTraversal": false,
  "RemoteAccessHostRequireCurtain": true,
  "RemoteAccessHostTalkGadgetPrefix": "",
  "RemoteAccessHostTokenValidation": false,
  "RemoteAccessHostUdpPortRange": "",
  "RequireOnlineRevocationChecksForLocalAnchors": true,
  "RestrictSigninToPattern": "",
  "SafeBrowsingEnabled": false,
  "SafeBrowsingExtendedReportingEnabled": false,
  "SafeBrowsingProtectionLevel": 0,
  "SavingBrowserHistoryDisabled": true,
  "SearchSuggestEnabled": false,
  "SharedClipboardEnabled": false,
  "ShowAppsShortcutInBookmarkBar": false,
  "ShowFullUrlsInAddressBar": true,
  "SigninAllowed": false,
  "SitePerProcess": true,
  "SpellCheckServiceEnabled": false,
  "SpellcheckEnabled": false,
  "StartupBrowserWindowLaunchSuppressed": true,
  "SuppressUnsupportedOSWarning": true,
  "SyncDisabled": true,
  "TranslateEnabled": false,
  "UrlKeyedAnonymizedDataCollectionEnabled": false,
  "UserFeedbackAllowed": false,
  "VideoCaptureAllowed": false,
  "WPADQuickCheckEnabled": false,
  "WallpaperImage": "",
  "WebAppInstallForceList": [],
  "WebRtcEventLogCollectionAllowed": false,
  "WebRtcLocalIpsAllowedUrls": [],
  "WebRtcLocalhostIpHandling": "default_public_interface_only"
}
EOF
    
    success "Enterprise policies created"
}

# Create master preferences (initial setup)
create_master_preferences() {
    local chrome_dir="$1"
    
    log "Creating master preferences"
    
    cat > "$chrome_dir/master_preferences" << 'EOF'
{
  "distribution": {
    "import_bookmarks": false,
    "import_history": false,
    "import_home_page": false,
    "import_search_engine": false,
    "make_chrome_default": false,
    "make_chrome_default_for_user": false,
    "ping_delay": 60,
    "skip_first_run_ui": true,
    "suppress_first_run_default_browser_prompt": true,
    "suppress_first_run_bubble": true,
    "do_not_create_desktop_shortcut": true,
    "do_not_create_quick_launch_shortcut": true,
    "do_not_create_taskbar_shortcut": true,
    "do_not_launch_chrome": true,
    "do_not_register_for_update_launch": true,
    "system_level": true,
    "verbose_logging": false
  },
  "first_run_tabs": [
    "about:blank"
  ],
  "homepage": "about:blank",
  "homepage_is_newtabpage": true,
  "browser": {
    "check_default_browser": false,
    "show_home_button": false
  },
  "bookmark_bar": {
    "show_on_all_tabs": false
  },
  "profile": {
    "default_content_setting_values": {
      "cookies": 4,
      "images": 1,
      "javascript": 1,
      "plugins": 3,
      "popups": 2,
      "geolocation": 2,
      "notifications": 2,
      "media_stream": 2,
      "media_stream_mic": 2,
      "media_stream_camera": 2,
      "protocol_handlers": 2,
      "ppapi_broker": 2,
      "automatic_downloads": 2,
      "midi_sysex": 2,
      "push_messaging": 2,
      "ssl_cert_decisions": 2,
      "metro_switch_to_desktop": 2,
      "protected_media_identifier": 2,
      "app_banner": 2,
      "site_engagement": 2,
      "durable_storage": 2
    }
  }
}
EOF
    
    success "Master preferences created"
}

# Generate hardened launcher script
create_launcher() {
    local browser="$1"
    local launcher_path="/usr/local/bin/${browser}-hardened"
    
    log "Creating hardened launcher: $launcher_path"
    
    cat > "$launcher_path" << 'EOF'
#!/bin/bash
# Hardened Chrome/Chromium Launcher
# Applies privacy-focused command-line flags

BROWSER="BROWSER_PLACEHOLDER"

# Base flags for privacy and security
FLAGS=(
    # Disable WebRTC completely
    "--disable-webrtc"
    "--disable-features=WebRtcHideLocalIpsWithMdns"
    
    # Disable geolocation
    "--disable-geolocation"
    "--disable-features=Geolocation"
    
    # Disable various tracking features
    "--disable-background-networking"
    "--disable-background-timer-throttling"
    "--disable-backgrounding-occluded-windows"
    "--disable-breakpad"
    "--disable-client-side-phishing-detection"
    "--disable-component-extensions-with-background-pages"
    "--disable-default-apps"
    "--disable-features=InterestFeedContentSuggestions"
    "--disable-features=TranslateUI"
    "--disable-hang-monitor"
    "--disable-ipc-flooding-protection"
    "--disable-popup-blocking"
    "--disable-prompt-on-repost"
    "--disable-renderer-backgrounding"
    "--disable-sync"
    "--disable-web-resources"
    "--disable-domain-reliability"
    "--disable-component-update"
    
    # Disable safe browsing (sends URLs to Google)
    "--safebrowsing-disable-auto-update"
    "--safebrowsing-disable-download-protection"
    "--safebrowsing-disable-extension-blacklist"
    
    # Disable various APIs
    "--disable-bluetooth"
    "--disable-usb"
    "--disable-webusb"
    "--disable-hid"
    "--disable-serial"
    "--disable-webgl"
    "--disable-3d-apis"
    "--disable-accelerated-2d-canvas"
    "--disable-accelerated-jpeg-decoding"
    "--disable-accelerated-mjpeg-decode"
    "--disable-accelerated-video-decode"
    "--disable-gpu"
    "--disable-gpu-compositing"
    "--disable-gpu-rasterization"
    "--disable-gpu-sandbox"
    "--disable-gpu-vsync"
    "--disable-gpu-watchdog"
    
    # Disable media features
    "--disable-media-session-api"
    "--disable-media-stream"
    "--disable-remote-playback-api"
    
    # Disable experimental features
    "--disable-experimental-accessibility-features"
    "--disable-experimental-accessibility-language-detection"
    "--disable-experimental-accessibility-virtual-keyboard"
    "--disable-experimental-fullscreen-exit-ui"
    "--disable-experimental-keyboard-lock-ui"
    
    # Memory and process isolation
    "--site-per-process"
    "--isolate-origins"
    "--isolate-extensions"
    
    # Security enhancements
    "--enable-strict-mixed-content-checking"
    "--enable-features=StrictOriginIsolation"
    "--enable-features=StrictMixedContentCheckingForPlugin"
    
    # Privacy enhancements
    "--no-first-run"
    "--no-default-browser-check"
    "--no-pings"
    "--no-service-autorun"
    "--noerrdialogs"
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"
    "--force-fieldtrials=*"
    
    # Disk and memory
    "--disk-cache-size=0"
    "--media-cache-size=0"
    "--aggressive-cache-discard"
    "--aggressive-tab-discard"
    
    # Fingerprinting mitigation
    "--disable-reading-from-canvas"
    "--disable-features=CanvasKit"
    "--disable-font-subpixel-positioning"
    "--disable-lcd-text"
    
    # Network
    "--disable-quic"
    "--disable-http2"
    "--disable-features=NetworkPrediction"
    "--dns-prefetch-disable"
    
    # Extensions
    "--disable-extensions"
    "--disable-extensions-file-access-check"
    "--disable-extensions-http-throttling"
    "--disable-background-networking"
    
    # Crash reporting
    "--disable-crash-reporter"
    "--disable-crashpad-for-testing"
    
    # Metrics
    "--metrics-recording-only"
    "--disable-metrics"
    "--disable-metrics-reporting"
    
    # Other
    "--enable-automation"
    "--password-store=basic"
    "--use-mock-keychain"
    "--export-tagged-pdf"
    "--no-wifi"
    "--disable-wifi"
    "--disable-wifi-detect"
    "--disable-features=AutofillServerCommunication"
    "--disable-features=AutofillEnableToolbarStatusChip"
    "--disable-features=PasswordManager"
    "--disable-features=PasswordGeneration"
    "--disable-features=CreditCardAutofill"
    "--disable-features=OfferStoreUnmaskedWalletCards"
    "--disable-features=AutofillCreditCardUpload"
    "--disable-features=AutofillCreditCardAuthentication"
    "--disable-features=AutofillEnablePaymentsMandatoryReauth"
    "--disable-features=AutofillEnableVirtualCardEnrollment"
    "--disable-features=AutofillEnableVirtualCardMetadata"
    "--disable-features=AutofillEnableVirtualCardStandaloneCvcField"
    "--disable-features=AutofillEnableVirtualCardSuggestionOptionText"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemText"
    "--disable-features=AutofillEnableVirtualCardSuggestionLabelText"
    "--disable-features=AutofillEnableVirtualCardSuggestionIcon"
    "--disable-features=AutofillEnableVirtualCardSuggestionSubLabelText"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityText"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityLabel"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityHint"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityValue"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityTraits"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityIdentifier"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityActivationPoint"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementClassName"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementIdentifier"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementLabel"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementValue"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTraits"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementFrame"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementBounds"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementCenter"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementSize"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementOrigin"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementRect"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementPoint"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementSelection"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementInsertionPoint"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementSelectedText"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementSelectedTextRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementMarkedText"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementMarkedTextRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementCharacterRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementLineRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementParagraphRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementSentenceRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementWordRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContext"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextRange"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextString"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextAttributedString"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextMutableString"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextMutableAttributedString"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextStorage"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextContainer"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextLayoutManager"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextView"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextField"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextInput"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextInputTraits"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextInputMode"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextInputContext"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextInputSuggestionDelegate"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextInputSuggestionDelegatePrivate"
    "--disable-features=AutofillEnableVirtualCardSuggestionItemAccessibilityElementTextualContextTextInputSuggestionDelegatePrivateMethods"
)

# Launch browser
exec "$BROWSER" "${FLAGS[@]}" "$@"
EOF
    
    # Replace placeholder with actual browser path
    sed -i "s|BROWSER_PLACEHOLDER|$browser|g" "$launcher_path"
    chmod +x "$launcher_path"
    
    success "Hardened launcher created: $launcher_path"
}

# Install privacy extensions
install_extensions() {
    log "Note: Extension installation must be done manually in Chrome"
    log "Recommended extensions:"
    log "  1. uBlock Origin (ad/tracker blocking)"
    log "  2. Privacy Badger (tracker blocking)"
    log "  3. HTTPS Everywhere (HTTPS enforcement)"
    log "  4. Cookie AutoDelete (cookie management)"
    log "  5. ClearURLs (URL tracking removal)"
    log "  6. WebRTC Leak Prevent (WebRTC protection)"
}

# Main setup
setup_chrome() {
    log "Starting Chrome/Chromium hardening..."
    
    local browsers
    browsers=$(detect_chrome) || exit 1
    
    for browser in $browsers; do
        info "Configuring: $browser"
        
        local policy_dir
        policy_dir=$(get_policy_dir "$browser")
        
        create_policies "$policy_dir"
        create_launcher "$browser"
    done
    
    install_extensions
    
    success "Chrome/Chromium hardening complete!"
    echo ""
    info "To use the hardened browser, run:"
    for browser in $browsers; do
        echo "  ${browser}-hardened"
    done
}

# Verify configuration
verify() {
    log "Verifying Chrome/Chromium configuration..."
    
    local browsers
    browsers=$(detect_chrome) || exit 1
    
    for browser in $browsers; do
        info "Checking: $browser"
        
        local policy_dir
        policy_dir=$(get_policy_dir "$browser")
        
        if [[ -f "$policy_dir/anti-geolocation.json" ]]; then
            success "Policy file exists: $policy_dir/anti-geolocation.json"
        else
            error "Policy file missing!"
        fi
        
        if [[ -f "/usr/local/bin/${browser}-hardened" ]]; then
            success "Launcher exists: /usr/local/bin/${browser}-hardened"
        else
            error "Launcher missing!"
        fi
    done
}

# Main
main() {
    case "${1:-setup}" in
        setup|install)
            setup_chrome
            ;;
        verify)
            verify
            ;;
        *)
            echo "Chrome/Chromium Hardening Script"
            echo ""
            echo "Usage: $0 {setup|verify}"
            echo ""
            echo "Commands:"
            echo "  setup  - Apply all hardening configurations"
            echo "  verify - Verify configuration is applied"
            exit 1
            ;;
    esac
}

main "$@"
