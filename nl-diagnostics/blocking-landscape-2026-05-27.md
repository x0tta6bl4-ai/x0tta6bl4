# Blocking Landscape: Russia And Global Context

Status date: 2026-05-28.

Scope: public reporting and technical monitoring on internet blocking,
VPN/circumvention restrictions, outages, and shutdowns relevant to the NL VPN
plan.

## Russia

Current direction: layered pressure rather than one simple VPN ban.

Latest verification on 2026-05-28 did not change the engineering conclusion:
the practical risk is a mix of Telegram/WhatsApp degradation, VPN fingerprint
blocking, and Russian platforms rejecting VPN/proxy exits while the VPN tunnel
itself may remain healthy.

Observed layers:

- Roskomnadzor reported restriction of 469 VPN services by the end of February
  2026. Kommersant described filtering by provider-side VPN traffic
  fingerprints.
- The Kremlin publicly said there is no user-level ban or liability for simply
  using VPN as of April 15, 2026, while MinTsifry said it is implementing
  measures to reduce VPN usage.
- Russian platforms and apps started limiting access for users with enabled VPN
  in April 2026; MinTsifry framed this as data-safety protection.
- Telecom operators are under pressure to route traffic through TSPU; courts
  issued fines/warnings for operators that violated TSPU requirements.
- Reports describe plans/targets to increase VPN blocking efficiency by 2030.
- Telegram and WhatsApp restrictions are part of the same trend: calls/media
  and service quality can degrade before a full block.
- OSW reported that in April 2026 Russia sharply intensified Telegram and VPN
  circumvention restrictions, and that more than 20 Russian websites/platforms
  were pushed to restrict users coming through VPNs.
- The Moscow Times confirmed visible VPN-user blocking on platforms such as
  Ozon and Kinopoisk and reported similar app disruptions around banking and
  ride-sharing services.
- Cloudflare reported in June 2025 that Russian ISPs throttled Cloudflare-backed
  services, including a 16 KB content-transfer pattern and disruption across
  HTTP/1.1, HTTP/2, and HTTP/3/QUIC.

Practical interpretation for our VPN:

- Expect protocol fingerprint blocking and IP reputation blocking.
- Expect Russian apps/sites to reject requests from known VPN/proxy exits even
  when the tunnel itself works.
- Expect mobile networks to behave differently from fixed-line ISPs.
- Expect partial failures: Telegram media, app login, banking/marketplace access,
  DNS, and QUIC may fail independently.
- Do not treat every client failure as an NL server outage.

## Global Context

Global trend: governments increasingly use both narrow blocking and broad
connectivity shutdowns.

Recent indicators:

- Access Now/#KeepItOn documented 313 internet shutdowns in 52 countries in
  2025, the highest count since 2016.
- Freedom House reports that anti-censorship tools, including VPNs, were blocked
  in at least 21 of 72 tracked countries over a five-year period.
- Cloudflare's Q1 2026 disruption review highlighted government-directed
  shutdowns in Uganda and Iran, plus disruptions from war, power outages, cable
  damage, and technical failures.
- Iran is the main 2026 extreme case: Cloudflare and AP reported partial
  restoration on May 26-27 after a near-three-month shutdown, with traffic still
  far below normal levels.

Operational watch signals for our VPN:

- one Russian platform rejects the VPN while generic HTTPS still works;
- Telegram web/API works but calls/media are slow or fail;
- mobile ISP and fixed-line ISP produce different results;
- direct path and SOCKS/VPN path disagree for the same target;
- Cloudflare/GitHub/OpenAI baseline targets all work but local Russian apps do
  not;
- NL transport ports fail from outside, which is a server/provider signal, not
  an app-blocking signal.

## Design Consequences

For the NL VPN plan, the important engineering points are:

1. Separate server health from censorship symptoms.
2. Keep read-only probes that classify: server down, provider issue, protocol
   blocked, exit IP rejected, app-specific block, DNS failure, mobile-only
   disruption.
3. Keep multiple client profiles and health hints, but do not auto-switch based
   on one app failure.
4. Treat SPB as inactive until explicitly reactivated; do not route recovery
   logic through it.
5. Preserve strict no-write gates on NL until there is explicit approval,
   current backup plan, rollback plan, and fresh read-only profile.

## Sources

- Kommersant, 2026-02-26:
  https://www.kommersant.ru/doc/8462883
- Vedomosti, 2026-04-15:
  https://www.vedomosti.ru/politics/news/2026/04/15/1190470-zapretov-vpn-net
- Interfax, 2026-04-15:
  https://www.interfax.ru/russia/1084061
- Vedomosti, 2026-04-27:
  https://www.vedomosti.ru/technology/news/2026/04/27/1193249-mintsifri-obyasnilo
- Vedomosti, 2026-04-06:
  https://www.vedomosti.ru/technology/news/2026/04/06/1188186-operatorov-oshtrafovali
- RBC, 2026-05-22:
  https://rt.rbc.ru/technology_and_media/21/05/2026/69ea464b9a794749c77ddf5d
- The Moscow Times, 2026-05-04:
  https://ru.themoscowtimes.com/2026/05/04/roskomnadzoru-postavili-zadachu-zablokirovat-92-vpn-k2030-godu-a194415
- OSW, 2026-04-17:
  https://www.osw.waw.pl/en/publikacje/analyses/2026-04-17/russia-blocks-telegram-and-cracks-down-vpns
- The Moscow Times, 2026-04-15:
  https://www.themoscowtimes.com/2026/04/15/russian-websites-begin-blocking-vpn-users-as-internet-controls-tighten-a92511
- Cloudflare, Russia throttling report, 2025-06-26:
  https://blog.cloudflare.com/russian-internet-users-are-unable-to-access-the-open-internet/
- Access Now/#KeepItOn, 2026-03-31:
  https://www.accessnow.org/tag/keepiton/
- Freedom House, Tunnel Vision report:
  https://freedomhouse.org/report/special-report/2025/tunnel-vision-anti-censorship-tools-end-end-encryption-and-fight-free
- Cloudflare Q1 2026 disruption summary:
  https://blog.cloudflare.com/q1-2026-internet-disruption-summary/
- Cloudflare Iran partial restoration, 2026-05-27:
  https://blog.cloudflare.com/iran-internet-partially-restored-may-2026/
- AP, Iran partial restoration, 2026-05-27:
  https://apnews.com/article/iran-war-internet-shutdown-restored-a9a473245d9c6a6fc41822d844847c17
