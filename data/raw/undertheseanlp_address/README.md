---
license: apache-2.0
---

# address - Vietnamese Address Converter

Chuyển đổi địa chỉ Việt Nam từ hệ thống hành chính cũ (63 tỉnh/thành phố, 3 cấp) sang hệ thống mới sau sáp nhập (34 tỉnh/thành phố, 2 cấp), có hiệu lực từ 01/07/2025.

## Technical Report

### 1. Bối cảnh

Nghị quyết của Quốc hội về sáp nhập đơn vị hành chính có hiệu lực ngày 01/07/2025, thay đổi cấu trúc hành chính Việt Nam:

| | Cũ | Mới |
|---|---|---|
| Tỉnh/Thành phố | 63 | 34 |
| Cấp hành chính | Tỉnh > Huyện > Xã | Tỉnh > Xã |
| Tổng số xã/phường | ~10,600 | ~3,300 |

Cấp huyện (quận/huyện/thị xã/thành phố trực thuộc tỉnh) bị loại bỏ hoàn toàn khỏi địa chỉ hành chính. Các xã/phường được sáp nhập, đổi tên, chia tách hoặc giữ nguyên tùy khu vực.

### 2. Kiến trúc hệ thống

```
address/
├── pyproject.toml                 # Package config (uv + hatchling)
├── data/
│   └── mapping.json               # 10,602 bản ghi mapping (4.7 MB)
├── src/
│   ├── __init__.py                # Public API
│   ├── models.py                  # Data models & enums
│   ├── normalizer.py              # Chuẩn hóa tiếng Việt
│   ├── parser.py                  # Phân tích chuỗi địa chỉ
│   ├── converter.py               # Logic chuyển đổi chính
│   └── cli.py                     # CLI (click)
├── scripts/
│   └── build_mapping.py           # Tạo mapping.json từ vietnamadminunits
└── tests/
    └── test_converter.py          # 13 test cases
```

**Nguyên tắc thiết kế**: Package hoạt động standalone — dữ liệu mapping được extract một lần từ `vietnamadminunits` (dev dependency) vào `data/mapping.json`, sau đó runtime chỉ cần `click` là dependency duy nhất.

### 3. Nguồn dữ liệu

Dữ liệu mapping được extract từ package `vietnamadminunits` v1.0.4 (PyPI, MIT license) thông qua script `scripts/build_mapping.py`. Package này cung cấp 3 file JSON chính:

| File | Nội dung | Kích thước |
|---|---|---|
| `converter_2025.json` | Mapping cũ → mới (province + ward) | 596 KB |
| `parser_legacy.json` | Dữ liệu hành chính cũ (63 tỉnh, 3 cấp) | 2.6 MB |
| `parser_from_2025.json` | Dữ liệu hành chính mới (34 tỉnh, 2 cấp) | 957 KB |

**Cấu trúc dữ liệu gốc** (trong `converter_2025.json`):

- `DICT_PROVINCE`: `{new_province_key: [old_province_key_1, old_province_key_2, ...]}` — mapping tỉnh
- `DICT_PROVINCE_WARD_NO_DIVIDED`: `{new_prov: {new_ward: [old_compound_key, ...]}}` — xã không bị chia tách
- `DICT_PROVINCE_WARD_DIVIDED`: `{new_prov: {old_compound_key: [{newWardKey, isDefaultNewWard, ...}]}}` — xã bị chia tách

Compound key format: `{province_key}_{district_key}_{ward_key}` (ví dụ: `thanhphohanoi_quanbadinh_phuongphucxa`).

### 4. Build mapping (`scripts/build_mapping.py`)

Script extract và chuẩn hóa dữ liệu từ 3 file JSON của vietnamadminunits thành một file `data/mapping.json` thống nhất:

```
uv run python scripts/build_mapping.py
```

**Output `mapping.json`** chứa:

| Trường | Mô tả |
|---|---|
| `metadata` | Source, version, effective_date, thống kê |
| `province_mapping` | `{old_key: new_key}` — 63 entries |
| `province_names` | `{key: {name, short, code}}` — 34 tỉnh mới |
| `old_province_names` | `{key: {name, short, code}}` — 63 tỉnh cũ |
| `ward_mapping` | List 10,602 records chi tiết |

**Mỗi ward mapping record** gồm:

```json
{
  "old_province": "Thành phố Hà Nội",
  "old_province_key": "thanhphohanoi",
  "old_district": "Quận Ba Đình",
  "old_district_key": "quanbadinh",
  "old_ward": "Phường Phúc Xá",
  "old_ward_key": "phuongphucxa",
  "new_province": "Thành phố Hà Nội",
  "new_province_key": "thanhphohanoi",
  "new_ward": "Phường Hồng Hà",
  "new_ward_key": "phuonghongha",
  "mapping_type": "merged"
}
```

**Phân loại mapping type:**

| Type | Số lượng | Mô tả |
|---|---|---|
| `unchanged` | 149 | Xã giữ nguyên tên |
| `renamed` | 92 | Xã đổi tên (1:1) |
| `merged` | 9,328 | Nhiều xã cũ gộp thành 1 xã mới |
| `divided` | 1,033 | 1 xã cũ chia thành nhiều xã mới |
| **Tổng** | **10,602** | |

**Logic phân loại:**
- `unchanged`: Chỉ có 1 compound key cũ trỏ vào ward mới VÀ tên trùng nhau
- `renamed`: Chỉ có 1 compound key cũ trỏ vào ward mới VÀ tên khác nhau
- `merged`: Nhiều compound key cũ cùng trỏ vào 1 ward mới
- `divided`: Từ `DICT_PROVINCE_WARD_DIVIDED`, có `is_default` flag cho mỗi option

### 5. Modules

#### 5.1 `src/models.py` — Data Models

- `MappingType(str, Enum)`: `UNCHANGED`, `RENAMED`, `MERGED`, `DIVIDED`
- `ConversionStatus(str, Enum)`: `SUCCESS`, `PARTIAL`, `NOT_FOUND`
- `AdminUnit(@dataclass)`: `province`, `district`, `ward`, `street` + `to_address()`
- `ConversionResult(@dataclass)`: `original`, `converted`, `status`, `mapping_type`, `old`, `new`, `note`

#### 5.2 `src/normalizer.py` — Chuẩn hóa tiếng Việt

**Ba hàm chính:**

| Hàm | Input | Output | Mô tả |
|---|---|---|---|
| `remove_diacritics()` | `"Phường Phúc Xá"` | `"Phuong Phuc Xa"` | Unicode NFKD decomposition + xử lý đ/Đ |
| `normalize_key()` | `"Quận Ba Đình"` | `"quanbadinh"` | Lowercase + bỏ dấu + bỏ space/punctuation |
| `expand_abbreviations()` | `"P.Phúc Xá, Q.Ba Đình"` | `"phường phúc xá, quận ba đình"` | Mở rộng viết tắt |

**Bảng viết tắt hỗ trợ:**

| Viết tắt | Đầy đủ |
|---|---|
| `TP.`, `T.P.` | Thành phố |
| `P.` | Phường |
| `Q.` | Quận |
| `H.` | Huyện |
| `TX.`, `T.X.` | Thị xã |
| `TT.`, `T.T.` | Thị trấn |
| `X.` | Xã |

#### 5.3 `src/parser.py` — Phân tích địa chỉ

Parse chuỗi địa chỉ theo format `"street, ward, district, province"` bằng phương pháp **right-to-left positional assignment**:

```
"123 Hàng Bông, Phường Phúc Xá, Quận Ba Đình, TP Hà Nội"
       ↑              ↑              ↑              ↑
    street          ward          district       province
   (parts[:-3])  (parts[-3])    (parts[-2])    (parts[-1])
```

Xử lý đặc biệt cho địa chỉ 2 phần (`"ward, province"`): kiểm tra prefix phường/xã/thị trấn để phân biệt với district.

#### 5.4 `src/converter.py` — Logic chuyển đổi

**Khởi tạo (lazy load):**
- Load `data/mapping.json` lần đầu khi gọi `convert_address()`
- Build index một lần, cache trong module-level globals

**Index structure:**

| Index | Key | Value | Mục đích |
|---|---|---|---|
| `province` | `old_prov_key` | `new_prov_key` | Tra cứu tỉnh |
| `province_keywords` | `normalized_name` | `old_prov_key` | Fuzzy match tên tỉnh |
| `exact` | `(prov, dist, ward)` | `[records]` | Tra cứu chính xác |
| `ward_only` | `(prov, ward)` | `[records]` | Tra cứu bỏ qua quận/huyện |

**Luồng chuyển đổi (`convert_address`):**

```
Input: "Phường Phúc Xá, Quận Ba Đình, Thành phố Hà Nội"
  │
  ├─ 1. parse_address() → AdminUnit(ward, district, province)
  │
  ├─ 2. Resolve province
  │     normalize("Thành phố Hà Nội") → "thanhphohanoi"
  │     province_mapping["thanhphohanoi"] → "thanhphohanoi"
  │     ❌ Không tìm thấy → NOT_FOUND
  │
  ├─ 3. Tra cứu ward (2-tier matching)
  │     ├─ Tier 1: exact("thanhphohanoi", "quanbadinh", "phuongphucxa") ✅
  │     └─ Tier 2: ward_only("thanhphohanoi", "phuongphucxa") (fallback)
  │
  ├─ 4. Chọn bản ghi tốt nhất
  │     └─ Nếu divided: ưu tiên is_default=true
  │
  └─ 5. Build result
        ConversionResult(converted="Phường Hồng Hà, Thành phố Hà Nội",
                         status=SUCCESS, mapping_type=MERGED)
```

**Conversion status:**

| Status | Điều kiện |
|---|---|
| `SUCCESS` | Tìm thấy cả province + ward mapping |
| `PARTIAL` | Chỉ tìm thấy province (ward không match) |
| `NOT_FOUND` | Không nhận dạng được province |

#### 5.5 `src/cli.py` — Command Line Interface

Hai commands, sử dụng `click`:

```bash
# Chuyển đổi 1 địa chỉ
address-convert convert "Phường Phúc Xá, Quận Ba Đình, TP Hà Nội"

# Chuyển đổi hàng loạt từ CSV
address-convert batch input.csv output.csv --column address
```

Batch mode đọc CSV, thêm 3 cột vào output: `converted_address`, `conversion_status`, `mapping_type`.

### 6. Test Results

13 test cases, tất cả pass:

```
tests/test_converter.py::TestMergedWard::test_phuc_xa_merged_to_hong_ha        PASSED
tests/test_converter.py::TestMergedWard::test_an_binh_can_tho                  PASSED
tests/test_converter.py::TestUnchangedWard::test_tan_loc_can_tho               PASSED
tests/test_converter.py::TestRenamedWard::test_long_hoa_renamed                PASSED
tests/test_converter.py::TestDividedWard::test_divided_selects_default         PASSED
tests/test_converter.py::TestAbbreviations::test_p_q_tp                        PASSED
tests/test_converter.py::TestAbbreviations::test_tp_shorthand                  PASSED
tests/test_converter.py::TestPartialAddress::test_province_only                PASSED
tests/test_converter.py::TestPartialAddress::test_unknown_province             PASSED
tests/test_converter.py::TestWithStreet::test_street_preserved                 PASSED
tests/test_converter.py::TestBatchConvert::test_batch                          PASSED
tests/test_converter.py::TestProvinceMapping::test_ha_noi_stays                PASSED
tests/test_converter.py::TestProvinceMapping::test_merged_province             PASSED
```

**Coverage theo loại test:**

| Nhóm test | Kiểm tra |
|---|---|
| Merged ward | Nhiều xã cũ → 1 xã mới (Phúc Xá → Hồng Hà) |
| Unchanged ward | Xã giữ nguyên (Tân Lộc) |
| Renamed ward | Xã đổi tên (Long Hòa → Long Tuyền) |
| Divided ward | Xã chia tách, chọn default |
| Abbreviations | `P.`, `Q.`, `TP.` mở rộng đúng |
| Partial address | Chỉ tỉnh, tỉnh không tồn tại |
| Street preserved | Giữ nguyên phần đường khi chuyển đổi |
| Batch convert | Chuyển đổi hàng loạt, mixed results |
| Province mapping | Tỉnh giữ nguyên, tỉnh sáp nhập |

### 7. Danh sách 34 tỉnh/thành phố mới

| Mã | Tên |
|---|---|
| 01 | Thành phố Hà Nội |
| 04 | Tỉnh Cao Bằng |
| 08 | Tỉnh Tuyên Quang |
| 11 | Tỉnh Điện Biên |
| 12 | Tỉnh Lai Châu |
| 14 | Tỉnh Sơn La |
| 15 | Tỉnh Lào Cai |
| 19 | Tỉnh Thái Nguyên |
| 20 | Tỉnh Lạng Sơn |
| 22 | Tỉnh Quảng Ninh |
| 24 | Tỉnh Bắc Ninh |
| 25 | Tỉnh Phú Thọ |
| 31 | Thành phố Hải Phòng |
| 33 | Tỉnh Hưng Yên |
| 37 | Tỉnh Ninh Bình |
| 38 | Tỉnh Thanh Hóa |
| 40 | Tỉnh Nghệ An |
| 42 | Tỉnh Hà Tĩnh |
| 44 | Tỉnh Quảng Trị |
| 46 | Thành phố Huế |
| 48 | Thành phố Đà Nẵng |
| 51 | Tỉnh Quảng Ngãi |
| 52 | Tỉnh Gia Lai |
| 56 | Tỉnh Khánh Hòa |
| 66 | Tỉnh Đắk Lắk |
| 68 | Tỉnh Lâm Đồng |
| 75 | Tỉnh Đồng Nai |
| 79 | Thành phố Hồ Chí Minh |
| 80 | Tỉnh Tây Ninh |
| 82 | Tỉnh Đồng Tháp |
| 86 | Tỉnh Vĩnh Long |
| 91 | Tỉnh An Giang |
| 92 | Thành phố Cần Thơ |
| 96 | Tỉnh Cà Mau |

### 8. Cách sử dụng

#### Python API

```python
from src import convert_address, batch_convert

# Chuyển đổi 1 địa chỉ
result = convert_address("Phường Phúc Xá, Quận Ba Đình, Thành phố Hà Nội")
print(result.converted)      # "Phường Hồng Hà, Thành phố Hà Nội"
print(result.status)         # ConversionStatus.SUCCESS
print(result.mapping_type)   # MappingType.MERGED

# Hỗ trợ viết tắt
result = convert_address("P. Phúc Xá, Q. Ba Đình, TP. Hà Nội")
print(result.converted)      # "Phường Hồng Hà, Thành phố Hà Nội"

# Batch
results = batch_convert(["addr1", "addr2", "addr3"])
```

#### CLI

```bash
# Cài đặt
uv sync

# Chuyển đổi 1 địa chỉ
uv run address-convert convert "P. Phúc Xá, Q. Ba Đình, TP Hà Nội"

# Chuyển đổi CSV
uv run address-convert batch input.csv output.csv --column address
```

#### Cập nhật mapping data

```bash
uv run python scripts/build_mapping.py
```

### 9. Hạn chế và hướng phát triển

**Hạn chế hiện tại:**
- Xã bị chia tách (`divided`): chỉ chọn ward mặc định (`is_default`), không hỗ trợ geocoding để chọn chính xác
- Parser dựa vào vị trí (right-to-left), có thể sai với địa chỉ không chuẩn format
- Chưa hỗ trợ input không dấu hoàn toàn (ví dụ: "Phuong Phuc Xa")

**Hướng phát triển:**
- Thêm geocoding cho divided wards (dựa trên tọa độ đường phố)
- Hỗ trợ input không dấu bằng fuzzy matching trên normalized keys
- Thêm REST API endpoint
- Tích hợp với pandas DataFrame cho batch processing lớn
