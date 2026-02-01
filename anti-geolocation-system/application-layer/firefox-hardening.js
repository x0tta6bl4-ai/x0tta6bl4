// Firefox Hardening Configuration
// Place in: ~/.mozilla/firefox/<profile>/user.js
// This file configures Firefox for maximum privacy and anti-fingerprinting

// ============================================================================
// LAYER 1: WEBRTC ELIMINATION
// ============================================================================

// Completely disable WebRTC to prevent IP leaks
user_pref("media.peerconnection.enabled", false);
user_pref("media.peerconnection.ice.default_address_only", true);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.relay_only", true);
user_pref("media.peerconnection.identity.enabled", false);
user_pref("media.peerconnection.mdns", false);
user_pref("media.peerconnection.turn.disable", true);
user_pref("media.peerconnection.use_document_iceservers", false);
user_pref("media.peerconnection.video.enabled", false);
user_pref("media.peerconnection.audio.enabled", false);

// Disable getUserMedia (camera/microphone access)
user_pref("media.navigator.enabled", false);
user_pref("media.navigator.video.enabled", false);
user_pref("media.navigator.audio.enabled", false);
user_pref("media.getusermedia.screensharing.enabled", false);
user_pref("media.getusermedia.browser.enabled", false);
user_pref("media.getusermedia.audiocapture.enabled", false);

// ============================================================================
// LAYER 2: GEOLOCATION API NEUTRALIZATION
// ============================================================================

// Disable geolocation completely
user_pref("geo.enabled", false);
user_pref("geo.provider.ms-windows-location", false);
user_pref("geo.provider.use_corelocation", false);
user_pref("geo.provider.use_gpsd", false);
user_pref("geo.provider.use_geoclue", false);
user_pref("geo.provider.network.url", "");
user_pref("geo.provider.network.logging.enabled", false);

// Default permission for geolocation (2 = always deny)
user_pref("permissions.default.geo", 2);

// ============================================================================
// LAYER 3: RESIST FINGERPRINTING (RFP)
// ============================================================================

// Enable Resist Fingerprinting (Tor Browser patches)
user_pref("privacy.resistFingerprinting", true);
user_pref("privacy.resistFingerprinting.autoDeclineNoUserInputCanvasPrompts", true);
user_pref("privacy.resistFingerprinting.letterboxing", true);
user_pref("privacy.resistFingerprinting.randomDataOnCanvasExtract", true);
user_pref("privacy.resistFingerprinting.randomDataOnCanvasExtract.pixel", 1);

// Spoof timezone to UTC
user_pref("privacy.resistFingerprinting.spoof TZ", true);

// Spoof screen resolution
user_pref("privacy.resistFingerprinting.spoof ScreenSize", true);

// ============================================================================
// LAYER 4: CANVAS/WEBGL/FONT FINGERPRINT RANDOMIZATION
// ============================================================================

// Canvas protection
user_pref("canvas.capturestream.enabled", false);
user_pref("canvas.filters.enabled", false);

// WebGL protection
user_pref("webgl.disabled", true);
user_pref("webgl.enable-webgl2", false);
user_pref("webgl.min_capability_mode", true);
user_pref("webgl.disable-extensions", true);
user_pref("webgl.disable-fail-if-major-performance-caveat", true);
user_pref("webgl.enable-debug-renderer-info", false);
user_pref("webgl.dxgl.enabled", false);
user_pref("webgl.enable-privileged-extensions", false);

// Disable WebGL debugging info that can be used for fingerprinting
user_pref("webgl.renderer-string-override", " ");
user_pref("webgl.vendor-string-override", " ");

// Font fingerprinting protection
user_pref("browser.display.use_document_fonts", 0);
user_pref("layout.css.font-loading-api.enabled", false);
user_pref("gfx.font_rendering.opentype_svg.enabled", false);

// Disable font cache (reduces fingerprinting surface)
user_pref("gfx.font_rendering.fontconfig.font.enabled", false);

// ============================================================================
// LAYER 5: AUDIO FINGERPRINTING PROTECTION
// ============================================================================

// Disable AudioContext API
user_pref("dom.webaudio.enabled", false);

// Alternative: Enable but with protection (if audio needed)
// user_pref("privacy.resistFingerprinting.block_mozAddonManager", true);

// ============================================================================
// LAYER 6: TRACKING PROTECTION
// ============================================================================

// Enable comprehensive tracking protection
user_pref("privacy.trackingprotection.enabled", true);
user_pref("privacy.trackingprotection.pbmode.enabled", true);
user_pref("privacy.trackingprotection.cryptomining.enabled", true);
user_pref("privacy.trackingprotection.fingerprinting.enabled", true);
user_pref("privacy.trackingprotection.socialtracking.enabled", true);

// Strict mode
user_pref("browser.contentblocking.category", "strict");

// ============================================================================
// LAYER 7: FIRST PARTY ISOLATION
// ============================================================================

// Enable First Party Isolation (FPI)
user_pref("privacy.firstparty.isolate", true);
user_pref("privacy.firstparty.isolate.restrict_opener_access", true);
user_pref("privacy.firstparty.isolate.use_site", true);

// ============================================================================
// LAYER 8: COOKIE AND STORAGE MANAGEMENT
// ============================================================================

// Total Cookie Protection (TCP)
user_pref("network.cookie.cookieBehavior", 5);

// Cookie settings
user_pref("network.cookie.thirdparty.sessionOnly", true);
user_pref("network.cookie.thirdparty.nonsecureSessionOnly", true);

// Clear cookies on shutdown
user_pref("privacy.sanitize.sanitizeOnShutdown", true);
user_pref("privacy.clearOnShutdown.cookies", true);
user_pref("privacy.clearOnShutdown.cache", true);
user_pref("privacy.clearOnShutdown.offlineApps", true);
user_pref("privacy.clearOnShutdown.sessions", true);
user_pref("privacy.clearOnShutdown.siteSettings", false);
user_pref("privacy.clearOnShutdown.history", false);
user_pref("privacy.clearOnShutdown.downloads", false);
user_pref("privacy.clearOnShutdown.formdata", false);

// Storage isolation
user_pref("browser.cache.cache_isolation", true);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.sessionstore.max_tabs_undo", 0);
user_pref("browser.sessionstore.max_windows_undo", 0);

// Disable storage APIs
user_pref("browser.storageManager.enabled", false);
user_pref("dom.storage.enabled", true);  // Keep enabled for basic functionality
user_pref("dom.storage.next_gen", true);
user_pref("dom.storage_access.enabled", false);

// IndexedDB
user_pref("dom.indexedDB.enabled", true);  // Required for many sites
user_pref("dom.indexedDB.experimental", false);

// ============================================================================
// LAYER 9: NETWORK AND CONNECTION SECURITY
// ============================================================================

// DNS over HTTPS (DoH)
user_pref("network.trr.mode", 2);  // 0=off, 1=reserved, 2=TRR preferred, 3=TRR only, 4=reserved, 5=off by default
user_pref("network.trr.uri", "https://mozilla.cloudflare-dns.com/dns-query");
user_pref("network.trr.bootstrapAddress", "1.1.1.1");
user_pref("network.trr.confirmationNS", "skip");
user_pref("network.trr.disable-ECS", true);
user_pref("network.trr.excluded-domains", "");
user_pref("network.trr.allow-rfc1918", false);

// Disable IPv6 (prevent IPv6 leaks)
user_pref("network.dns.disableIPv6", true);
user_pref("network.http.fast-fallback-to-IPv4", false);

// Proxy DNS when using SOCKS
user_pref("network.proxy.socks_remote_dns", true);

// Disable speculative connections
user_pref("network.http.speculative-parallel-limit", 0);
user_pref("network.predictor.enabled", false);
user_pref("network.predictor.enable-prefetch", false);
user_pref("network.prefetch-next", false);
user_pref("network.dns.disablePrefetch", true);
user_pref("network.dns.disablePrefetchFromHTTPS", true);

// Disable captive portal detection
user_pref("network.captive-portal-service.enabled", false);
user_pref("network.connectivity-service.enabled", false);

// ============================================================================
// LAYER 10: REFERER AND HEADER CONTROL
// ============================================================================

// Referer control
user_pref("network.http.referer.XOriginPolicy", 2);
user_pref("network.http.referer.XOriginTrimmingPolicy", 2);
user_pref("network.http.referer.spoofSource", false);
user_pref("network.http.referer.defaultPolicy", 2);
user_pref("network.http.referer.defaultPolicy.pbmode", 2);

// Send only scheme, host, port in referer
user_pref("network.http.referer.trimmingPolicy", 1);

// ============================================================================
// LAYER 11: USER AGENT AND CLIENT HINTS
// ============================================================================

// RFP handles UA spoofing, but we can reinforce
user_pref("general.useragent.override", "");  // Let RFP handle it
user_pref("general.buildID.override", "20100101");
user_pref("general.appversion.override", "5.0 (Windows)");
user_pref("general.platform.override", "Win32");
user_pref("general.oscpu.override", "Windows NT 10.0; Win64; x64");

// Disable client hints (reduce fingerprinting)
user_pref("network.http.accept-encoding.secure", "gzip, deflate, br");
user_pref("dom.netinfo.enabled", false);

// ============================================================================
// LAYER 12: TELEMETRY AND DATA COLLECTION DISABLE
// ============================================================================

// Disable all telemetry
user_pref("toolkit.telemetry.enabled", false);
user_pref("toolkit.telemetry.unified", false);
user_pref("toolkit.telemetry.archive.enabled", false);
user_pref("toolkit.telemetry.newProfilePing.enabled", false);
user_pref("toolkit.telemetry.shutdownPingSender.enabled", false);
user_pref("toolkit.telemetry.updatePing.enabled", false);
user_pref("toolkit.telemetry.bhrPing.enabled", false);
user_pref("toolkit.telemetry.firstShutdownPing.enabled", false);
user_pref("toolkit.telemetry.coverage.opt-out", true);
user_pref("toolkit.coverage.opt-out", true);
user_pref("toolkit.coverage.endpoint.base", "");

// Disable health reports
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);

// Disable studies
user_pref("app.shield.optoutstudies.enabled", false);
user_pref("app.normandy.enabled", false);
user_pref("app.normandy.api_url", "");

// Disable crash reports
user_pref("breakpad.reportURL", "");
user_pref("browser.tabs.firefox-view", false);
user_pref("browser.tabs.firefox-view-next", false);

// ============================================================================
// LAYER 13: SAFE BROWSING (OPTIONAL - DISABLE FOR MAXIMUM PRIVACY)
// ============================================================================

// Disable Safe Browsing (sends URLs to Google)
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.safebrowsing.phishing.enabled", false);
user_pref("browser.safebrowsing.downloads.enabled", false);
user_pref("browser.safebrowsing.downloads.remote.enabled", false);
user_pref("browser.safebrowsing.downloads.remote.url", "");
user_pref("browser.safebrowsing.downloads.remote.block_potentially_unwanted", false);
user_pref("browser.safebrowsing.downloads.remote.block_uncommon", false);
user_pref("browser.safebrowsing.provider.google.updateURL", "");
user_pref("browser.safebrowsing.provider.google.gethashURL", "");
user_pref("browser.safebrowsing.provider.google4.updateURL", "");
user_pref("browser.safebrowsing.provider.google4.gethashURL", "");

// ============================================================================
// LAYER 14: SEARCH AND URL BAR
// ============================================================================

// Disable search suggestions
user_pref("browser.search.suggest.enabled", false);
user_pref("browser.urlbar.suggest.searches", false);
user_pref("browser.urlbar.speculativeConnect.enabled", false);
user_pref("browser.urlbar.dnsResolveSingleWordsAfterSearch", 0);

// Disable live search engines
user_pref("browser.search.update", false);
user_pref("browser.search.geoSpecificDefaults", false);
user_pref("browser.search.geoSpecificDefaults.url", "");

// ============================================================================
// LAYER 15: AUTOFILL AND FORM SECURITY
// ============================================================================

// Disable autofill
user_pref("browser.formfill.enable", false);
user_pref("extensions.formautofill.addresses.enabled", false);
user_pref("extensions.formautofill.creditCards.enabled", false);
user_pref("extensions.formautofill.heuristics.enabled", false);

// Disable password manager (use external password manager)
user_pref("signon.rememberSignons", false);
user_pref("signon.autofillForms", false);
user_pref("signon.formlessCapture.enabled", false);

// ============================================================================
// LAYER 16: MEDIA AND DRM
// ============================================================================

// Disable DRM
user_pref("media.eme.enabled", false);
user_pref("media.gmp-widevinecdm.enabled", false);
user_pref("media.gmp-widevinecdm.visible", false);
user_pref("media.gmp-provider.enabled", false);

// Disable media autoplay
user_pref("media.autoplay.default", 5);
user_pref("media.autoplay.blocking_policy", 2);

// ============================================================================
// LAYER 17: EXTENSION SECURITY
// ============================================================================

// Extension restrictions
user_pref("extensions.webextensions.restrictedDomains", "");
user_pref("extensions.getAddons.showPane", false);
user_pref("extensions.htmlaboutaddons.recommendations.enabled", false);
user_pref("browser.discovery.enabled", false);

// Disable pocket
user_pref("extensions.pocket.enabled", false);
user_pref("extensions.pocket.api", "");
user_pref("extensions.pocket.oAuthConsumerKey", "");
user_pref("extensions.pocket.showHome", false);
user_pref("extensions.pocket.site", "");

// ============================================================================
// LAYER 18: PERFORMANCE AND HARDWARE
// ============================================================================

// Limit hardware information exposure
user_pref("dom.maxHardwareConcurrency", 2);
user_pref("device.sensors.enabled", false);
user_pref("device.sensors.orientation.enabled", false);
user_pref("device.sensors.motion.enabled", false);
user_pref("device.sensors.proximity.enabled", false);
user_pref("device.sensors.ambientLight.enabled", false);

// Disable battery API
user_pref("dom.battery.enabled", false);

// Disable gamepad API
user_pref("dom.gamepad.enabled", false);
user_pref("dom.gamepad.extensions.enabled", false);
user_pref("dom.gamepad.haptic_feedback.enabled", false);

// Disable VR
user_pref("dom.vr.enabled", false);
user_pref("dom.vr.oculus.enabled", false);
user_pref("dom.vr.openvr.enabled", false);
user_pref("dom.vr.puppet.enabled", false);

// ============================================================================
// LAYER 19: MISCELLANEOUS PRIVACY SETTINGS
// ============================================================================

// Disable beacon API
user_pref("beacon.enabled", false);

// Disable ping attributes
user_pref("browser.send_pings", false);
user_pref("browser.send_pings.require_same_host", true);

// Disable UITour
user_pref("browser.uitour.enabled", false);
user_pref("browser.uitour.url", "");

// Disable reader mode parse-on-load
user_pref("reader.parse-on-load.enabled", false);

// Disable mid-click paste
user_pref("middlemouse.paste", false);

// Disable clipboard events
user_pref("dom.event.clipboardevents.enabled", false);

// Disable page thumbnails
user_pref("browser.pagethumbnails.capturing_disabled", true);

// Disable screenshot tool (uses cloud)
user_pref("extensions.screenshots.disabled", true);

// ============================================================================
// LAYER 20: SECURITY ENHANCEMENTS
// ============================================================================

// Strict HTTPS-only mode
user_pref("dom.security.https_only_mode", true);
user_pref("dom.security.https_only_mode_ever_enabled", true);

// Certificate settings
user_pref("security.cert_pinning.enforcement_level", 2);
user_pref("security.remote_settings.crlite_filters.enabled", true);
user_pref("security.pki.crlite_mode", 2);

// Mixed content
user_pref("security.mixed_content.block_active_content", true);
user_pref("security.mixed_content.block_display_content", true);
user_pref("security.mixed_content.block_object_subrequest", true);

// Disable insecure renegotiation
user_pref("security.ssl.require_safe_negotiation", true);
user_pref("security.ssl.treat_unsafe_negotiation_as_broken", true);
user_pref("security.tls.enable_0rtt_data", false);

// OCSP
user_pref("security.OCSP.enabled", 1);
user_pref("security.OCSP.require", true);

// ============================================================================
// END OF CONFIGURATION
// ============================================================================

// Note: After applying this configuration:
// 1. Restart Firefox completely
// 2. Verify at https://browserleaks.com/canvas
// 3. Verify at https://browserleaks.com/webrtc
// 4. Verify at https://coveryourtracks.eff.org
// 5. Test WebGL at https://browserleaks.com/webgl
