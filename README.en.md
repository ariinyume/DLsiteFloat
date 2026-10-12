# DLsiteFloat - Floating window & status bar subtitles for DLsiteSound

[简体中文](README.md) | [繁體中文](README.zh-TW.md) | **English**

> An LSPosed / Xposed module that pins a **floating subtitle window** synced with playback progress onto the **playback page** of DLsiteSound (the DLsite audio app), and can also mirror subtitles to the **system status bar** (injected inside the SystemUI process).

- Current version: **2.3.1** (`DLsiteFloat-2.3.1-code1006-debug.apk`, package `io.github.ariinyume.dlsitesoundfloat`)
- 📦 Download APK: [Releases · v2.3.1](https://github.com/ariinyume/DLsiteFloat/releases/tag/v2.3.1)
- 📝 Development progress: [DLsiteFloat 插件开发进度管理](https://my.feishu.cn/wiki/CQoMwY4nFilzLkkrzG4cy44fnoh) (in Chinese)
- ⭐ Xposed repository: [DLsiteFloat - DLsiteSound floating window / status bar subtitle module](https://github.com/Xposed-Modules-Repo/io.github.ariinyume.dlsitesoundfloat)


---


## Features

- **Two pill buttons on the playback page (since 2.0.1)**: two MD3 pill buttons sit side by side above the playback control bar — on the left `Status ON / Status OFF` (**the whole button disappears when there are no subtitles**), on the right `Popup ON / Popup OFF / No Sub`.
  - `Status OFF`: status bar subtitles are off
  - `Status ON`: status bar subtitles are on
  - `Popup OFF`: the floating window is closed
  - `Popup ON`: the floating window is open
  - `No Sub`: the current audio track has no subtitles available
  - **Fixed button size (since 2.1.2)**: width, height, corner radius, text and offset from the seek bar are computed only from the density **locked in on first launch**; the text uses **fixed px** and auto-fits the available pill width so it is **always fully visible**, and is unaffected by later changes to the system "Font size / Display size".
  - **Multilingual support (since 2.1.2)**: the module's display language follows the **system language** (read from system configuration, unaffected by the host app's "App language"), supporting **简体中文 / 繁體中文 / English**.
    | System language | Left / right button | Button `No Sub` | Floating window placeholder |
    | --- | --- | --- | --- |
    | 简体中文 | `状态栏 开 / 关`, `悬浮窗 开 / 关` | `无字幕` | `无字幕` |
    | 繁體中文 | `狀態欄 開 / 關`, `懸浮窗 開 / 關` | `無字幕` | `無字幕` |
    | Other languages | `Status ON / OFF`, `Popup ON / OFF` | `No Sub` | `No Subtitles` |
    
- **Status bar subtitles (since 2.0.1)**: **mirrors the current subtitle line to the system status bar** — a persistent `FrameLayout` is injected into the SystemUI process, and the app process pushes subtitle lines to it via a **cross-process broadcast**. Toggled by a single tap on the `Status ON / Status OFF` pill button on the left of the playback page. See [docs/statusbar-subtitle.md](docs/statusbar-subtitle.md).
  - **One-way leftward scrolling** (replaces the system marquee's bounce-back loop): scrolling follows the cue duration, and a new line settles before it starts scrolling, so long subtitles no longer bounce back and forth.
  - **Covers the clock / notification icon area**: while showing, the status bar clock and the notification icon area are hidden and notifications become a numeric badge; everything is restored when it ends.
  - **Fluid Cloud avoidance**: the subtitle's right edge dynamically stops just left of Fluid Cloud (`seeding_card_container`); when Fluid Cloud is absent it fills up to a fixed left bound (38dp). A 24px hysteresis band keeps the width from jumping as Fluid Cloud comes and goes.

- **Visual settings page (since 2.2.0)**: the module ships its own settings page; changes take effect as soon as you tap "Save settings".
  - **Status card**: the three states — "whether the module is active / whether SystemUI is authorized / whether DLsiteSound is running" — each get their own guidance, and the whole page is disabled while the module is inactive.
  - **Main subtitle / active line**: subtitle color, shadow color, shadow strength, shadow radius, active line opacity, active line scale.
  - **Inactive lines**: blur inactive lines + blur radius, scale inactive lines + scale ratio.
  - **Typography**: alignment (left / center / right), line spacing, extra spacing for wrapped lines inside a long subtitle, panel color.
  - **Live preview panel**: the preview re-renders in sync while you tweak the parameters.
  - **Liquid glass tuning (since 2.3.0)**: its own card, placed **before** the "More" card; a master switch + four sliders (backdrop brightness / transparency / brightness / blur strength) + reset to defaults.
  - **Language**: switch between **简体中文 / 繁體中文 / English** on the spot inside the page (independent of the playback-page button language setting).
  - **More**: master switch for status bar subtitles, the **debug log** toggle (since 2.2.7, off by default), subtitle config backup & restore (export / import JSON), restart SystemUI.

- **In-process floating window**: the window hangs directly inside the DLsiteSound process (`WindowManager` + `TYPE_APPLICATION_OVERLAY`) and shares the same `SubtitleRepository` instance with all the hooks, so it needs **no cross-process IPC and no separate Service**.
  - **Draggable / resizable**: press anywhere on the panel and drag to move it; drag the bottom-right handle to resize (default 85% screen width × 200dp, minimum 140×72dp, **never taller than half the screen**).
  - **Two ways to dismiss the in-panel close button**: tap the panel once and a ✕ appears; **it hides itself if you don't tap within 5 s**; while it is showing, **tapping an empty part of the panel retracts it immediately**.
  - **The floating window can be used on its own**: when the `com.android.systemui` scope is not authorized, the `Status ON / Status OFF` button on the left is not shown.

- **Liquid glass floating window (since 2.3.0)**: the floating window panel and the playback-page subtitle buttons can be switched to a **liquid glass** look — the "background blur" is done by the **system compositor** (zero permissions, zero capture, zero extra power draw), while the glass itself is drawn by the module as 8 stacked material layers (rounded clipping / adaptive frost / top-and-bottom light response / grain frosting / refracted edge light / inner thin edge light). See [docs/液态玻璃实现与可调参数.md](docs/液态玻璃实现与可调参数.md) for details.
  - **Its own card**: the "**Liquid glass tuning**" card is separate — liquid glass (master switch), backdrop brightness, transparency, brightness, blur strength, reset liquid glass defaults. **When the master switch is off, everything below it is hidden.**
  - Once liquid glass is on, "Panel color" can no longer be adjusted (the glass would cover the solid color).

- **Subtitle alignment by playback progress**: subtitle lines are aligned against the player's (`ExoPlayer` / expo audio) real playback progress.

- **Automatic subtitle capture**: intercepts DLsiteSound's network responses (okhttp3) and scans the response body directly for `webvtt` / `subtitles` subtitle JSON, parsing it on the spot — it **does not rely on URL keywords**, so it still works with obfuscated or repackaged okhttp3. The subtitle source is DLsiteSound's official `play.dl.dlsitesound.com/.../optimized/xxx.json`, delivered per audio track.

- **Smart track switching**: when you switch to an audio track with no subtitles, handling is suspended first and the floating window shows a `No Subtitles` placeholder while it waits for the new track's subtitle JSON — **5 s** when there are no cached cues, relaxed to **15 s** when cached cues exist; if no JSON arrives within **5 s** the window is **closed early**, and it is **automatically reopened** once the JSON arrives; only if the arbitration window expires with still no JSON are the cues cleared and the state judged to be "no subtitles". See [docs/track-change.md](docs/track-change.md).

- **Permission guidance and graceful degradation**: when overlay permission has not been granted, the first tap jumps to the "Display over other apps" settings page, and it **only prompts once**.


---


## Compatibility

| Item | Description |
| --- | --- |
| **Target app** | DLsiteSound (`jp.co.eisys.dlsitesound`) |
| **Framework** | LSPosed **2.2.0+** (since 2.0.0 it uses the modern libxposed API; the legacy API and the modern API must not be mixed) |
| **Scopes** | **Two** must be checked: `jp.co.eisys.dlsitesound` (host app: floating window + playback page buttons) and `com.android.systemui` (status bar subtitles) |
| **libxposed API** | `minApiVersion=101` / `targetApiVersion=102`, configured in `META-INF/xposed/module.prop`. Since 2.0.0 it **no longer** uses `de.robv.android.xposed:api:82` or the four `xposed*` meta-data entries |
| **Android version** | `minSdk 24` (Android 7.0) and up; `targetSdk / compileSdk 34`. Android 8.0+ uses `TYPE_APPLICATION_OVERLAY`, lower versions fall back to `TYPE_PHONE` |
| **Device / ROM** | Tested and adapted for **ONEPLUS / ColorOS**, and should also work on OxygenOS / RealmeUI in theory; other vendors' ROMs should work too as long as overlay / permission behaviour is normal |
| **Requirement** | Only works when the official server provides subtitles for that audio track (optimized subtitle JSON) |
| **Not applicable** | Apps other than DLsiteSound; devices that are not rooted or have no Xposed framework installed; DRM-restricted content that has no subtitles at all |

> ⚠️ Adaptation depends on the target app's internal implementation (view structure, player class names, network stack), so **a major app update may break the module**; it then has to be re-adapted for the new version.


---



## Tested on

- Software version: DLsiteSound 2.20.2

- Device 1: OnePlus 15, ColorOS 17.0.0.102 (CN01B110P02), KernelSU 3.3.0 (32601-2) · LSPosed 2.2.1 (7912)
- Device 2: OnePlus 12, ColorOS 16.0.10.501 (CN01B110P02), SukiSU 4.2.0 (40900-2) · LSPosed 2.2.1 (7912)

---


## Getting started

1. **Get the module**: build it yourself (see [docs/build.md](docs/build.md)), or download `DLsiteFloat-<version>-debug.apk` from the releases page. All settings are documented in [docs/settings.md](docs/settings.md).
2. **Install and enable**: install the APK on a rooted device → open **LSPosed Manager** or a similar module manager → enable this module → **check both** scopes: **`jp.co.eisys.dlsitesound`** + **`com.android.systemui`** → **force stop** DLsiteSound, then **restart SystemUI or reboot your phone**.
3. **Grant overlay permission**:
   - Settings → Apps → DLsiteSound & DLsiteFloat → Permissions → Special app access → `Display over other apps`.
   - If needed, also allow `Show windows while running in the background`.
4. **Open a playback page that has subtitles**: two pill buttons appear above the playback control bar.
   - Left `Status ON / Status OFF`: tap to toggle **status bar subtitles** (off by default); the button does not appear when there are no subtitles or when the `com.android.systemui` scope is not authorized.
   - Right `Popup ON / Popup OFF`: tap to toggle the **floating window**.
   - With no subtitles it shows `No Sub` and the floating window cannot be opened.
   - When you leave the playback page (back to the home page / list page, etc.) the buttons hide automatically; neither the floating window nor the status bar subtitles are hidden with the page.
5. **Operating the floating window**: press anywhere on the panel and drag to move it; drag the bottom-right handle to resize. Tapping the panel (not the handle) toggles the close button (✕, 30dp display / hit area) in the top-right corner; tap ✕ to close the window.
6. The floating window subtitles and the status bar subtitles can be used at the same time without interfering with each other.
7. **Adjust subtitle appearance**: use the **"DLsiteFloat 设置"** app icon on your launcher, or find this module in your module manager, to open the visual settings page; changes take effect as soon as you tap "Save settings" (status-bar-subtitle changes only refresh after "Restart SystemUI").
8. **Want the liquid glass look**: on the same settings page → the "Liquid glass tuning" card → turn on the master switch, then adjust the four sliders to taste (**Backdrop brightness** should match how bright the current page is; the other three default to `50`) → tap "Save settings".


---


## Feedback

- **GitHub Issues**: please file them in the Issues section of the project repository, and include as much of the following as you can:
  1. Your device model / Android version / ROM (in particular whether it is ColorOS / HyperOS / stock / near-stock, etc.)
  2. The DLsiteSound version you are using
  3. Reproduction steps + the LSPosed log (filtered by `DLsiteSoundFloat`) + `dlsitefloat_net.log` when relevant + screen recording / screenshots (please redact or crop out any sensitive information)
- **Before filing, please confirm**: that you installed the latest APK (check the `==== BUILD 2.3.1 / code 1006` line in the LSPosed log)
- **When troubleshooting track switching / subtitle capture problems**: turn on the **debug log** under "More" on the settings page and reproduce the issue once more (it is off by default and will flood the log if left on; remember to turn it back off afterwards).
- **Liquid glass issues**: first try "setting blur strength back to 50–60", "not maxing out transparency" and "matching backdrop brightness to how bright the page is"; if it is still wrong, attach the LSPosed log (filtered by `DLsiteSoundFloat`) and state your **device model / ROM** (compositor blur support varies between ROMs).

- File an issue: <https://github.com/ariinyume/DLsiteFloat/issues>


---


## Disclaimer

1. This project is mainly for personal technical research / learning purposes; the author **does not encourage or recommend** using it commercially.
2. This module is developed with AI assistance. It can only be guaranteed that no human subjective malicious input or malicious behaviour was involved during development. AI-generated code may not fully match the development intent — please verify it yourself before use.
3. This project only studies **client-side subtitle display behaviour**. It does not bypass any DRM, and it does not modify or extract the copyright-protected audio / text content itself. Subtitle files are delivered by DLsiteSound's official servers — please respect the rights of the content owners, and buy and support works through official channels.
4. This module has **no affiliation or partnership** with DLsiteSound (eisys Co., Ltd.) or with any phone manufacturer.
5. Using this module requires **Root and an Xposed framework**. It may violate the warranty terms of some devices or the security policy of some ROMs, and may lead to consequences such as system instability, loss of warranty or security risks; **you bear any and all such risk yourself**. The author **accepts no responsibility** for any problem caused by using this module (including but not limited to account issues, device instability, data loss, etc.), and recommends backing up your frequently used device data promptly and periodically.
6. Adaptation depends on the target app's internal implementation, and an app update may break the module; the author **does not guarantee** that the module will remain usable long-term or work on every version / device.
7. Downloading or using this module is taken as acceptance of the above terms.


---


## Credits

- Status bar subtitle effect reference: [ColorOS Mod](https://github.com/rikumi/coloros-mod)
- Subtitle settings feature reference: [ColorOS-Live-Lyrics-Bridge](https://github.com/Andrea-lyz/ColorOS-Live-Lyrics-Bridge?tab=readme-ov-file)
- UI reference: [KernelSU](https://github.com/tiann/KernelSU), [LSPosed](https://github.com/LSPosed/LSPosed)

---
