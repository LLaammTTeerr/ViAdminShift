=== VietAddr – Vietnam 2-Level Address for WooCommerce ===
Contributors: vnwooplugins
Tags: woocommerce, vietnam, address, checkout, phone
Requires at least: 6.0
Tested up to: 7.1
Requires PHP: 7.4
Stable tag: 0.2.0
License: GPL-3.0-or-later
License URI: https://www.gnu.org/licenses/gpl-3.0.html

2-level Province → Ward addresses for Vietnam (2025 merger, 34 provinces, no district level) for the Checkout Block and classic checkout.

== Description ==

Since 1 July 2025 Vietnam uses a 2-level administrative system: 34 provinces/cities and 3,321 wards/communes/special zones. VietAddr turns the WooCommerce address form into two dependent dropdowns for Vietnamese addresses:

* **Province** (Tỉnh/Thành phố) uses the core `state` field: 34 entries.
* **Ward** (Xã/Phường/Đặc khu) uses the core `city` field, filtered by the selected province. The ward name is stored, so addresses stay readable in emails, exports and other plugins.
* Postcode is hidden for Vietnam.
* Phone numbers must have 10 digits starting with 0 or +84 (03/05/07/08/09); they are saved as `0xxxxxxxxx`.

Works with:

* the Checkout block and the classic `[woocommerce_checkout]` shortcode,
* My Account > Addresses,
* the admin order screen (ward dropdown filtered by province),
* High-Performance Order Storage (HPOS).

**Migrating from "Vietnam Checkout for WooCommerce"** (woo-vietnam-checkout): Tools > "VietAddr: chuyển địa chỉ" converts saved customer addresses (old 3-level province/district/ward codes, or that plugin's 2-level codes) to the new format. It has a dry-run mode, backs up old values to the user meta `_vnck_legacy_address`, and lists the addresses that need a manual fix (for example, an old ward split between several new wards). WP-CLI: `wp vnck migrate-legacy [--apply]`.

Tiếng Việt: Plugin thay ô địa chỉ của WooCommerce bằng 2 ô chọn Tỉnh/Thành phố → Xã/Phường/Đặc khu (34 tỉnh, 3.321 xã theo đơn vị hành chính từ 01/07/2025), ẩn mã bưu chính, kiểm số điện thoại Việt Nam. Dùng được với Checkout Block, checkout cổ điển, Tài khoản > Địa chỉ, màn sửa đơn trong admin, HPOS.

= Data =

Administrative units are bundled in `data/vn-units.json` (source: provinces.open-api.vn API v2, see `data/SOURCE.md`). The plugin makes no external requests: the browser loads the JSON file from your own site.

= Credits and data sources =

* Administrative units (34 provinces/cities, 3,321 wards/communes/special zones, per the 2025 merger resolutions): source is the Vietnam National Statistics Office (Cục Thống kê, https://danhmuchanhchinh.nso.gov.vn/), downloaded through the API https://provinces.open-api.vn/ by Nguyễn Hồng Quân (https://github.com/hongquan/vn-open-api-provinces), licensed GPL-3.0-or-later. Download date and SHA-256 are in `data/SOURCE.md`.
* The old-to-new ward conversion table (`data/legacy-map.json`) also uses data from the plugin "Vietnam Checkout for WooCommerce" (woo-vietnam-checkout) 2.1.6 (GPL), and the old-ward mapping of the same API.
* This plugin is licensed GPL-3.0-or-later; the full text is in the `LICENSE` file.

== Installation ==

1. Upload the `vietaddr` folder to `/wp-content/plugins/` or install the zip from Plugins > Add New.
2. Activate the plugin. WooCommerce 8.0 or newer is required.
3. Set the store country to Vietnam if needed. No settings page is required.

== Frequently Asked Questions ==

= Does it replace the city/state fields in the Checkout block? =

The block keeps the core fields. Province is the core state dropdown. For the ward, a small script places a dropdown over the core city field and writes the value through the WooCommerce Blocks data store. The server checks again when the order is placed, so an invalid ward or phone is rejected even without JavaScript.

= Can I change the phone rule? =

Yes, with the `vnck_phone_pattern` filter (PHP regular expression applied to the normalized number).

= What happens to addresses saved by version 0.1.0? =

Version 0.1.0 stored ward codes. They are still accepted and shown as ward names; the migration tool converts them to names.

= What is removed when I delete the plugin? =

The plugin creates no options or transients. Deleting it from Plugins (uninstall) removes only the user meta `_vnck_legacy_address`, the backup written by the migration tool. Customer and order addresses (WooCommerce billing/shipping fields) are kept. Deactivating the plugin removes nothing.

== Screenshots ==

1. Checkout block: province and ward dropdowns.
2. Order received page with ward and province names.
3. Admin order screen: ward dropdown filtered by province.

== Changelog ==

= 0.2.0 =
* Renamed from "VN Checkout" to VietAddr (slug `vietaddr`).
* Checkout block support (ward dropdown, server-side validation through the Store API).
* Ward name is stored in the city field (ward codes from 0.1.0 still accepted).
* Admin order screen: ward dropdown.
* Migration tool and WP-CLI command for "Vietnam Checkout for WooCommerce" addresses.
* Text domain `vietaddr`, translation template `languages/vietaddr.pot`.
* Uninstall removes the migration backup meta `_vnck_legacy_address`.
* License changed to GPL-3.0-or-later; data credits added.

= 0.1.0 =
* Classic checkout and My Account: province/ward dropdowns, Vietnamese phone validation, HPOS compatibility.

== Upgrade Notice ==

= 0.2.0 =
Adds Checkout block support. New addresses store the ward name instead of the ward code.
