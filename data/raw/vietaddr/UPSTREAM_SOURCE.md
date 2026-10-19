# Nguồn dữ liệu đơn vị hành chính

- Nguồn: provinces.open-api.vn, API v2 (đơn vị hành chính 2 cấp sau sáp nhập 2025)
- URL: https://provinces.open-api.vn/api/v2/?depth=2
- Ngày tải: 2026-10-06 (HTTP Date: Tue, 06 Oct 2026 09:19:37 GMT), HTTP 200, 613.422 byte
- SHA-256 file thô (`_raw/p2.json`): e997eb9dcbbbafbbae00496965572f8ccd6e192cbb1024e8fe6b5513c162dc9b
- Xử lý: `python3 -I tools/build_units.py _raw/p2.json data/vn-units.json`
- Kết quả: 34 tỉnh/thành; 3.321 xã/phường/đặc khu (687 phường, 2.621 xã, 13 đặc khu). Khớp con số 3.321 công bố.
- Mã: tỉnh 2 chữ số, xã 5 chữ số (mã gốc của nguồn, đệm 0). Trong WooCommerce mã tỉnh lưu dạng `VN` + 2 số (vd `VN01`) để khoá mảng luôn là chuỗi.

# Bảng chuyển dữ liệu plugin cũ (`data/legacy-map.json`)

- Xã cũ → xã mới: provinces.open-api.vn API v2, `/api/v2/w/<mã xã mới>/to-legacies/` cho từng xã mới (3321 lượt gọi, tải 2026-10-06 bằng curl vào `_raw/legacy/`; `/api/v1/version` báo `data_version 2026-09-20`).
- Khoá tỉnh của plugin cũ "Vietnam Checkout for WooCommerce" 2.1.6 (`https://downloads.wordpress.org/plugin/woo-vietnam-checkout.2.1.6.zip`, SHA-256 `350667fdd87ecdf5156d6a821958b4fa0319c7828ef7599e8fad69a453cb64c2`): chỉ đọc các file `cities/*.php` như dữ liệu (không chạy) để lấy khoá tỉnh (`HANOI`, `01`…) và kiểm mã xã mới của plugin đó. Giấy phép plugin cũ: header ghi GPLv3, license.txt ghi GPLv2 "or any later version".
- Xử lý: `python3 -I tools/build_legacy.py _raw/legacy _raw/oldplugin/src/woo-vietnam-checkout/cities data/vn-units.json data/legacy-map.json`
- Kết quả: 9.583 xã cũ ánh xạ 1-1; 440 xã cũ bị chia cho nhiều xã mới (không tự chuyển); 22 xã cũ trong plugin cũ không có trong nguồn; 691 quận/huyện cũ; 126 khoá tỉnh cũ (63 dạng số + 63 dạng tên); 34 khoá tỉnh mới. Mã xã mới của plugin cũ khớp 3.275/3.321, 45 chỉ khác vị trí dấu (Hòa/Hoà), 1 khác mã (`23737` Xã Ia Mơ → `23938`, ghi ở `new_code_fix`).
- SHA-256 `data/legacy-map.json`: `2c3d729efabbcadcc8afaf3a5666f682234afe2d6aaf5692b8c86f47d429277e`
