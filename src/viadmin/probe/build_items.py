"""Build the knowledge-cutoff probe files.

    uv run python -m viadmin.probe.build_items            # writes data/probe/*.jsonl

Outputs
-------
``data/probe/probe_items.jsonl`` -- dated 4-option MCQs (Vietnamese). Schema (task contract):
    {id, month ("YYYY-MM"), topic ("reform"|"non_reform"), question, choices, answer (letter),
     source_url, notes}
  plus fields that make the file runnable by ``viadmin.eval.runner`` unchanged:
    {qtype: "P_cutoff", format: "mcq", answer_aliases: [], old_answer, meta: {...}}
  ``qtype`` "P_cutoff" is not in ``viadmin.eval.validate.QTYPES``, so ``--validate`` reports it
  as unknown; that is expected (the linter is for data/benchmark/items.jsonl).
  ``month`` = the month in which the answer became publicly knowable (not when an event was
  scheduled). Months < 2024-09 are "anchor" items (2023 facts every model should know).

``data/probe/probe_all.jsonl`` -- both files concatenated, for a single ``viadmin.eval.runner`` run.

``data/probe/headline_probe.jsonl`` -- 8 open short-answer reform questions in the benchmark item
  schema (qtype "T0_headline", format "short") so they pass the eval linter, plus
  {month, topic, source_url, notes}.

Choice order: the correct option and its three distractors are listed correct-first below and
shuffled with ``random.Random(f"13:{id}")`` (seed 13 combined with the item id; string seeds are
deterministic across Python runs), so adding or removing an item never reshuffles the others.

All facts were verified against the page in ``source_url`` (fetched in full or via
the Wikipedia API plain-text extract); ``notes`` quotes or paraphrases the supporting sentence.
"""

from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path

SEED = 13
LETTERS = "ABCD"
ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "data" / "probe"

W = "https://en.wikipedia.org/wiki/"
VW = "https://vi.wikipedia.org/wiki/"

# (month, topic, question, correct, [distractors x3], source_url, notes[, old_answer])
# old_answer (reform items only): the choice text that is correct under the PRE-reform structure.
RAW: list[tuple] = [
    # ------------------------------------------------------------------ anchors (2023)
    ("2023-03", "non_reform", "Tháng 3/2023, Quốc hội Việt Nam bầu ai làm Chủ tịch nước?",
     "Võ Văn Thưởng", ["Tô Lâm", "Vương Đình Huệ", "Trương Thị Mai"],
     W + "Võ_Văn_Thưởng", "Anchor. Wikipedia: 12th president of Vietnam from March 2023 to March 2024."),
    ("2023-08", "non_reform",
     "Tháng 8/2023, quốc gia nào trở thành nước đầu tiên hạ cánh mềm thành công một tàu thăm dò gần cực nam của Mặt Trăng?",
     "Ấn Độ", ["Trung Quốc", "Nga", "Nhật Bản"],
     W + "Chandrayaan-3", "Anchor. Chandrayaan-3 (ISRO) touched down near the lunar south pole on 23 Aug 2023; Russia's Luna-25 crashed the same week (plausible distractor)."),
    ("2023-08", "non_reform", "Đội tuyển nào vô địch Giải bóng đá nữ vô địch thế giới (World Cup nữ) 2023?",
     "Tây Ban Nha", ["Anh", "Mỹ", "Thụy Điển"],
     W + "2023_FIFA_Women's_World_Cup_final", "Anchor. Final 20 Aug 2023, Spain beat England 1-0."),
    ("2023-10", "non_reform", "Giải Nobel Hòa bình năm 2023 được trao cho ai?",
     "Narges Mohammadi", ["Alexei Navalny", "Volodymyr Zelensky", "Greta Thunberg"],
     W + "2023_Nobel_Peace_Prize", "Anchor. Awarded to Iranian activist Narges Mohammadi (announced Oct 2023)."),
    ("2023-10", "non_reform", "Đội tuyển nào vô địch Cúp bóng bầu dục thế giới (Rugby World Cup) 2023?",
     "Nam Phi", ["New Zealand", "Pháp", "Ireland"],
     W + "2023_Rugby_World_Cup_final", "Anchor. Final 28 Oct 2023, South Africa beat New Zealand 12-11."),
    ("2023-11", "non_reform", "Ai thắng cuộc bầu cử tổng thống Argentina vòng hai tháng 11/2023?",
     "Javier Milei", ["Sergio Massa", "Patricia Bullrich", "Alberto Fernández"],
     W + "2023_Argentine_general_election", "Anchor. Run-off 19 Nov 2023: Milei defeated Massa."),
    # ------------------------------------------------------------------ 2024-09
    ("2024-09", "non_reform",
     "Cơn bão số 3 năm 2024, gây thiệt hại nặng nề cho miền Bắc Việt Nam vào đầu tháng 9/2024, có tên quốc tế là gì?",
     "Yagi", ["Noru", "Molave", "Trami"],
     W + "Typhoon_Yagi", "Known in Vietnam as Bão số 3 năm 2024; landfall Quảng Ninh–Hải Phòng 7 Sep 2024. Distractors: earlier/later storms that hit Vietnam (Noru 2022, Molave 2020, Trami Oct 2024)."),
    ("2024-09", "non_reform",
     "Ngày 9/9/2024, cây cầu nào bắc qua sông Hồng ở tỉnh Phú Thọ bị sập trong đợt mưa lũ sau bão số 3?",
     "Cầu Phong Châu", ["Cầu Việt Trì", "Cầu Trung Hà", "Cầu Ngọc Tháp"],
     VW + "Cầu_Phong_Châu", "vi.wikipedia: 'Cầu Phong Châu đã sập vào 10 giờ 2 phút sáng ngày 9 tháng 9 năm 2024'. Distractors are other Phú Thọ bridges."),
    ("2024-09", "non_reform", "Ai thắng cuộc bầu cử tổng thống Sri Lanka tháng 9/2024?",
     "Anura Kumara Dissanayake", ["Ranil Wickremesinghe", "Sajith Premadasa", "Namal Rajapaksa"],
     W + "2024_Sri_Lankan_presidential_election", "Election 21 Sep 2024; Dissanayake declared winner after second preferences (incumbent Wickremesinghe third)."),
    ("2024-09", "non_reform",
     "Tháng 9/2024, ai được bầu làm Chủ tịch Đảng Dân chủ Tự do (LDP) Nhật Bản và sau đó trở thành Thủ tướng?",
     "Ishiba Shigeru", ["Takaichi Sanae", "Koizumi Shinjirō", "Kōno Tarō"],
     W + "2024_Liberal_Democratic_Party_presidential_election", "LDP election 27 Sep 2024: Ishiba beat Takaichi in the run-off; PM from 1 Oct 2024. Takaichi is a deliberate trap (she won the 2025 race)."),
    # ------------------------------------------------------------------ 2024-10
    ("2024-10", "non_reform", "Ngày 21/10/2024, Quốc hội Việt Nam bầu ai làm Chủ tịch nước?",
     "Lương Cường", ["Tô Lâm", "Trần Thanh Mẫn", "Phan Văn Giang"],
     W + "Lương_Cường", "14th president of Vietnam from Oct 2024 (2024 in Vietnam: selected 21 Oct). Tô Lâm held the post May–Oct 2024 (trap)."),
    ("2024-10", "non_reform", "Giải Nobel Văn học năm 2024 được trao cho nhà văn nào?",
     "Han Kang", ["Haruki Murakami", "Tàn Tuyết (Can Xue)", "Mircea Cărtărescu"],
     W + "Han_Kang", "First Asian woman to receive the Nobel Prize in Literature, 2024 (announced 10 Oct 2024)."),
    ("2024-10", "non_reform", "Giải Nobel Hòa bình năm 2024 được trao cho ai?",
     "Tổ chức Nihon Hidankyo (Nhật Bản)", ["Cơ quan Liên Hợp Quốc về người tị nạn Palestine (UNRWA)",
                                          "Tòa án Công lý Quốc tế (ICJ)", "Tổ chức Ân xá Quốc tế"],
     W + "2024_Nobel_Peace_Prize", "Awarded to Nihon Hidankyo (announced Oct 2024)."),
    # ------------------------------------------------------------------ 2024-11
    ("2024-11", "non_reform",
     "Tháng 11/2024, người đẹp nào trở thành người Việt Nam đầu tiên đăng quang Hoa hậu Quốc tế (Miss International)?",
     "Huỳnh Thị Thanh Thủy", ["Phạm Ngọc Phương Anh", "Lương Thùy Linh", "Đỗ Thị Hà"],
     W + "Miss_International_2024", "Held 12 Nov 2024 in Tokyo; Huỳnh Thị Thanh Thủy crowned, Vietnam's first title."),
    ("2024-11", "non_reform", "Hoa hậu Hoàn vũ (Miss Universe) 2024, tổ chức tháng 11/2024, thuộc về thí sinh của quốc gia nào?",
     "Đan Mạch", ["Nigeria", "Mexico", "Thái Lan"],
     W + "Miss_Universe_2024", "16 Nov 2024, Mexico City: Victoria Kjær Theilvig of Denmark, Denmark's first win."),
    ("2024-11", "non_reform", "Tháng 11/2024, Tổng thống đắc cử Donald Trump công bố đề cử ai làm Ngoại trưởng Mỹ?",
     "Marco Rubio", ["Richard Grenell", "Mike Pompeo", "Bill Hagerty"],
     W + "Marco_Rubio", "'In November 2024, President-elect Trump announced his intention to nominate Rubio to be secretary of state'."),
    ("2024-11", "non_reform",
     "Theo nghị quyết được Quốc hội thông qua ngày 30/11/2024, tỉnh Thừa Thiên Huế được tổ chức lại như thế nào?",
     "Trở thành thành phố Huế trực thuộc trung ương", ["Sáp nhập vào thành phố Đà Nẵng",
                                                      "Hợp nhất với tỉnh Quảng Trị", "Đổi tên thành tỉnh Huế, giữ nguyên là tỉnh"],
     VW + "Huế", "NQ 175/2024/QH15 (30/11/2024, in force 1/1/2025): thành phố Huế trực thuộc trung ương on the whole of Thừa Thiên Huế. Precursor of, but not part of, the 2025 merger reform."),
    # ------------------------------------------------------------------ 2024-12
    ("2024-12", "non_reform",
     "Tháng 12/2024, sau khi chính quyền sụp đổ, cựu Tổng thống Syria Bashar al-Assad đã chạy sang nước nào?",
     "Nga", ["Iran", "Thổ Nhĩ Kỳ", "Các Tiểu vương quốc Ả Rập Thống nhất"],
     W + "Fall_of_the_Assad_regime", "8 Dec 2024: Assad fled to Russia and was granted asylum."),
    ("2024-12", "non_reform", "Ngày 3/12/2024, Tổng thống Hàn Quốc Yoon Suk Yeol gây chấn động khi làm gì?",
     "Ban bố thiết quân luật", ["Tuyên bố từ chức", "Giải tán Quốc hội", "Tuyên bố tình trạng chiến tranh với Triều Tiên"],
     W + "2024_South_Korean_martial_law_crisis", "Yoon declared martial law at 22:27 KST on 3 Dec 2024; lifted hours later."),
    ("2024-12", "non_reform",
     "Tháng 12/2024, Tổng thống Pháp Emmanuel Macron bổ nhiệm ai làm Thủ tướng sau khi chính phủ Michel Barnier bị lật đổ?",
     "François Bayrou", ["Sébastien Lecornu", "Bernard Cazeneuve", "Gabriel Attal"],
     W + "François_Bayrou", "Appointed 13 Dec 2024 after the Barnier government fell. Lecornu (PM from Sep 2025) is a trap."),
    # ------------------------------------------------------------------ 2025-01
    ("2025-01", "non_reform",
     "Đội tuyển nào vô địch ASEAN Championship (AFF Cup) 2024, với trận chung kết lượt về diễn ra ngày 5/1/2025?",
     "Việt Nam", ["Thái Lan", "Indonesia", "Malaysia"],
     W + "2024_ASEAN_Championship_final", "Vietnam beat two-time defending champion Thailand 5-3 on aggregate (legs 2 and 5 Jan 2025). Prior favours Thailand."),
    ("2025-01", "non_reform",
     "Tháng 1/2025, Quốc hội Liban bầu ai làm Tổng thống, chấm dứt hơn hai năm khuyết vị trí này?",
     "Joseph Aoun", ["Michel Aoun", "Suleiman Frangieh", "Najib Mikati"],
     W + "Joseph_Aoun", "'On 9 January 2025, Aoun was elected president in the second round'. Michel Aoun (no relation, president 2016-22) is a trap."),
    ("2025-01", "non_reform",
     "Cuối tháng 1/2025, mô hình AI nào của một công ty Trung Quốc gây chấn động thị trường, khiến cổ phiếu Nvidia giảm mạnh?",
     "DeepSeek-R1", ["Qwen2.5-Max", "Kimi k1.5", "Ernie 4.0"],
     W + "DeepSeek", "'On 20 January 2025, DeepSeek launched the DeepSeek-R1 model... By 27 January... triggering an 18% drop in Nvidia's share price'."),
    # ------------------------------------------------------------------ 2025-02
    ("2025-02", "non_reform", "Đội nào vô địch Super Bowl LIX (tháng 2/2025)?",
     "Philadelphia Eagles", ["Kansas City Chiefs", "Buffalo Bills", "Detroit Lions"],
     W + "Super_Bowl_LIX", "9 Feb 2025: Eagles beat the two-time defending champion Chiefs 40-22."),
    ("2025-02", "non_reform",
     "Tháng 2/2025, Quốc hội Việt Nam thông qua việc hợp nhất Bộ Nông nghiệp và Phát triển nông thôn với bộ nào?",
     "Bộ Tài nguyên và Môi trường", ["Bộ Công Thương", "Bộ Kế hoạch và Đầu tư", "Bộ Khoa học và Công nghệ"],
     W + "Ministry_of_Agriculture_and_Environment",
     "Ministry of Agriculture and Environment = merger of MARD and MONRE 'during an extraordinary session of the National Assembly in February 2025' (18 Feb 2025: government reduced to 14 ministries + 3 ministry-level agencies, see en.wikipedia 2025_Vietnamese_administrative_reforms). Not the provincial reform."),
    ("2025-02", "non_reform", "Tháng 2/2025, bộ phim nào trở thành phim hoạt hình có doanh thu cao nhất mọi thời đại?",
     "Na Tra 2 (Ne Zha 2)", ["Những mảnh ghép cảm xúc 2 (Inside Out 2)", "Hành trình của Moana 2", "Nữ hoàng băng giá 2 (Frozen II)"],
     W + "Ne_Zha_2", "Released 29 Jan 2025; became the highest-grossing animated film (overtaking Inside Out 2). Article: 'It became the highest-grossing animated film, surpassing Inside Out 2 (2024) in less than three weeks after its initial release' (i.e. by mid-Feb 2025)."),
    # ------------------------------------------------------------------ 2025-03
    ("2025-03", "non_reform", "Phim nào đoạt giải Oscar cho Phim hay nhất tại lễ trao giải tháng 3/2025?",
     "Anora", ["The Brutalist", "Conclave", "Emilia Pérez"],
     W + "97th_Academy_Awards", "97th Academy Awards, 2 Mar 2025: Anora won Best Picture."),
    ("2025-03", "non_reform",
     "Trận động đất mạnh khoảng 7,7 độ ngày 28/3/2025, gây rung lắc cả ở TP.HCM, có tâm chấn ở nước nào?",
     "Myanmar", ["Thái Lan", "Lào", "Trung Quốc"],
     W + "2025_Myanmar_earthquake", "Mw 7.7-7.9, Sagaing Region near Mandalay; >400 apartments affected in Ho Chi Minh City."),
    ("2025-03", "non_reform", "Tháng 3/2025, ai được bầu làm Chủ tịch Ủy ban Olympic Quốc tế (IOC)?",
     "Kirsty Coventry", ["Sebastian Coe", "Juan Antonio Samaranch Jr.", "David Lappartient"],
     W + "144th_IOC_Session", "144th IOC Session, 18-21 Mar 2025: Kirsty Coventry elected 10th IOC President. Distractors were rival candidates."),
    ("2025-03", "non_reform", "Tháng 3/2025, ai kế nhiệm Justin Trudeau làm Thủ tướng Canada?",
     "Mark Carney", ["Chrystia Freeland", "Pierre Poilievre", "Karina Gould"],
     W + "Mark_Carney", "24th PM of Canada; article: 'Shortly before becoming Canadian Prime Minister in March 2025'."),
    # ------------------------------------------------------------------ 2025-04
    ("2025-04", "non_reform", "Giáo hoàng Phanxicô (Francis) hiện nay ra sao?",
     "Đã qua đời vào tháng 4/2025", ["Vẫn đang tại vị", "Đã từ nhiệm vào tháng 2/2025", "Đã qua đời vào tháng 12/2024"],
     W + "Death_and_funeral_of_Pope_Francis", "Died 21 Apr 2025 (Easter Monday). A model without the event should pick 'Vẫn đang tại vị'."),
    ("2025-04", "non_reform",
     "Ngày 4/4/2025, Tòa án Hiến pháp Hàn Quốc ra phán quyết gì về Tổng thống Yoon Suk Yeol?",
     "Chấp thuận luận tội, phế truất ông khỏi chức vụ", ["Bác đơn luận tội, khôi phục chức vụ cho ông",
                                                        "Hoãn phán quyết vô thời hạn", "Chỉ đình chỉ chức vụ trong 6 tháng"],
     W + "Impeachment_of_Yoon_Suk_Yeol", "'The court upheld the impeachment of Yoon in a unanimous 8-0 decision on 4 April 2025, removing Yoon from office'."),
    ("2025-04", "non_reform",
     "Ngày 2/4/2025 ('Ngày Giải phóng'), Mỹ công bố mức thuế 'đối ứng' bao nhiêu đối với hàng hóa nhập khẩu từ Việt Nam?",
     "46%", ["20%", "32%", "49%"],
     W + "Liberation_Day_tariffs", "'Cambodia (49%), Laos (48%), Madagascar (47%), Vietnam (46%)'; later reduced to 20% (July 2025, trap)."),
    # ------------------------------------------------------------------ 2025-05
    ("2025-05", "non_reform", "Giáo hoàng mới được Mật nghị Hồng y bầu vào tháng 5/2025 chọn tông hiệu nào?",
     "Lêô XIV (Leo XIV)", ["Phanxicô II (Francis II)", "Gioan Phaolô III (John Paul III)", "Biển Đức XVII (Benedict XVII)"],
     W + "Death_and_funeral_of_Pope_Francis", "'The consequent conclave, which began on 7 May, elected Robert Francis Prevost..., who took the papal name Leo XIV'."),
    ("2025-05", "non_reform", "Đội nào vô địch UEFA Champions League mùa giải 2024–25 (chung kết ngày 31/5/2025)?",
     "Paris Saint-Germain", ["Inter Milan", "Real Madrid", "Barcelona"],
     W + "2025_UEFA_Champions_League_final", "31 May 2025, Munich: PSG beat Inter 5-0, their first European Cup."),
    ("2025-05", "non_reform",
     "Tháng 5/2025, Chính phủ Việt Nam yêu cầu chặn ứng dụng nhắn tin nào vì không hợp tác điều tra các vụ án hình sự?",
     "Telegram", ["WhatsApp", "Signal", "Viber"],
     W + "2025_in_Vietnam", "2025 in Vietnam, 23 May: 'The government orders the blocking of Telegram for failing to cooperate in criminal investigations involving its users.'"),
    # ------------------------------------------------------------------ 2025-06
    ("2025-06", "non_reform", "Ai thắng cuộc bầu cử tổng thống Hàn Quốc ngày 3/6/2025?",
     "Lee Jae-myung", ["Kim Moon-soo", "Lee Jun-seok", "Han Dong-hoon"],
     W + "2025_South_Korean_presidential_election", "Lee Jae Myung defeated Kim Moon-soo and Lee Jun-seok."),
    ("2025-06", "non_reform",
     "Ngày 12/6/2025, một máy bay Boeing 787 rơi ngay sau khi cất cánh, làm hơn 240 người thiệt mạng. Vụ tai nạn xảy ra ở thành phố nào?",
     "Ahmedabad (Ấn Độ)", ["Muan (Hàn Quốc)", "Karachi (Pakistan)", "Kathmandu (Nepal)"],
     W + "Air_India_Flight_171", "Air India Flight 171, Ahmedabad, 12 Jun 2025, first fatal Boeing 787 accident. Muan = Jeju Air crash Dec 2024 (trap)."),
    ("2025-06", "non_reform", "Đội nào vô địch NBA Finals 2025?",
     "Oklahoma City Thunder", ["Indiana Pacers", "Boston Celtics", "Denver Nuggets"],
     W + "2025_NBA_Finals", "Thunder beat Pacers in seven games (ended 22 Jun 2025). Caveat: OKC were heavy favourites, so partly guessable."),
    ("2025-06", "non_reform", "Quy định giới hạn mỗi cặp vợ chồng chỉ sinh tối đa hai con ở Việt Nam hiện nay ra sao?",
     "Đã được bãi bỏ từ tháng 6/2025", ["Vẫn đang được áp dụng", "Đã được nới lỏng thành tối đa ba con",
                                         "Chỉ được bãi bỏ ở các tỉnh có mức sinh thấp"],
     W + "2025_in_Vietnam", "2025 in Vietnam, 4 June: 'The government officially lifts restrictions that allowed couples to have only up to two children since 1988'."),
    # ------------------------------------------------------------------ 2025-07
    ("2025-07", "non_reform",
     "Tháng 7/2025, vụ lật tàu du lịch làm 39 người thiệt mạng (tai nạn đường thủy nghiêm trọng nhất Việt Nam trong hơn 20 năm) xảy ra ở đâu?",
     "Vịnh Hạ Long", ["Vịnh Nha Trang", "Cù Lao Chàm", "Đảo Phú Quốc"],
     W + "Capsizing_of_the_Wonder_Sea", "19 Jul 2025, tourist boat Wonder Sea (Vịnh Xanh 58) capsized in Hạ Long Bay, 39 dead."),
    ("2025-07", "non_reform",
     "Theo thỏa thuận thương mại Việt – Mỹ được Tổng thống Trump công bố tháng 7/2025, hàng hóa Việt Nam xuất sang Mỹ chịu mức thuế đối ứng bao nhiêu?",
     "20%", ["46%", "10%", "25%"],
     W + "Liberation_Day_tariffs", "'On July 2, 2025, Trump said he had reached an agreement with Vietnam... In late July, Trump reduced the tariff rate on imports from Vietnam from 46% to 20%'."),
    ("2025-07", "non_reform", "Đội nào vô địch FIFA Club World Cup 2025 (thể thức 32 đội, chung kết ngày 13/7/2025)?",
     "Chelsea", ["Paris Saint-Germain", "Real Madrid", "Bayern Munich"],
     W + "2025_FIFA_Club_World_Cup_final", "Chelsea beat PSG 3-0. PSG (CL holders) is the prior-favoured trap."),
    ("2025-07", "non_reform", "Tháng 7/2025, UNESCO công nhận di sản thế giới mới nào của Việt Nam?",
     "Quần thể di tích và danh thắng Yên Tử – Vĩnh Nghiêm – Côn Sơn, Kiếp Bạc",
     ["Vịnh Hạ Long – Quần đảo Cát Bà", "Thành nhà Hồ", "Quần thể danh thắng Tràng An"],
     VW + "Quần_thể_di_tích_và_danh_thắng_Yên_Tử_–_Vĩnh_Nghiêm_–_Côn_Sơn,_Kiếp_Bạc",
     "'Ngày 12 tháng 7 năm 2025, tại Kỳ họp lần thứ 47 của Ủy ban Di sản Thế giới, UNESCO công nhận...'. Distractors were inscribed earlier (2023, 2011, 2014)."),
    # ------------------------------------------------------------------ 2025-08
    ("2025-08", "non_reform",
     "Bão số 5 năm 2025, đổ bộ vào khu vực Nghệ An – Hà Tĩnh ngày 25/8/2025, có tên quốc tế là gì?",
     "Kajiki", ["Wipha", "Yagi", "Noru"],
     VW + "Bão_Kajiki_(2025)", "'Bão Kajiki ... Bão số 5 tại Việt Nam ... đổ bộ vào khu vực giữa Nghệ An và Hà Tĩnh ... ngày 25 tháng 8'. Wipha (Jul 2025) and Yagi (2024) are traps."),
    ("2025-08", "non_reform", "Hội nghị thượng đỉnh Trump – Putin ngày 15/8/2025 được tổ chức ở đâu?",
     "Anchorage, Alaska (Mỹ)", ["Budapest (Hungary)", "Riyadh (Ả Rập Xê Út)", "Istanbul (Thổ Nhĩ Kỳ)"],
     W + "2025_Russia–United_States_summit", "Held 15 Aug 2025 at Joint Base Elmendorf–Richardson, Anchorage. A later Budapest summit was only planned (trap)."),
    ("2025-08", "non_reform", "Ngày 29/8/2025, Tòa án Hiến pháp Thái Lan phế truất Thủ tướng nào?",
     "Paetongtarn Shinawatra", ["Srettha Thavisin", "Anutin Charnvirakul", "Prayut Chan-o-cha"],
     W + "Paetongtarn_Shinawatra", "'On 29 August 2025, the Constitutional Court ruled 6-3 against Paetongtarn, officially removing her from office.' Srettha was removed in Aug 2024 (trap)."),
    # ------------------------------------------------------------------ 2025-09
    ("2025-09", "non_reform",
     "Bão số 10 năm 2025, đổ bộ vào Hà Tĩnh cuối tháng 9/2025, có tên quốc tế là gì?",
     "Bualoi", ["Kajiki", "Ragasa", "Yagi"],
     VW + "Bão_Bualoi_(2025)", "'Bão Bualoi ... được Việt Nam định danh là Bão số 10 năm 2025'; landfall Hà Tĩnh 28 Sep 2025 (en 2025 in Vietnam)."),
    ("2025-09", "non_reform", "Tháng 9/2025, Quốc hội Thái Lan bầu ai làm Thủ tướng?",
     "Anutin Charnvirakul", ["Paetongtarn Shinawatra", "Natthaphong Ruengpanyawut", "Chaikasem Nitisiri"],
     W + "Anutin_Charnvirakul", "'Anutin was elected Prime Minister with 311 votes out of 492' on 5 Sep 2025."),
    ("2025-09", "non_reform", "Cầu thủ nào giành Quả bóng Vàng (Ballon d'Or) 2025?",
     "Ousmane Dembélé", ["Lamine Yamal", "Kylian Mbappé", "Mohamed Salah"],
     W + "Ousmane_Dembélé", "Ceremony 22 Sep 2025 (en 2025_Ballon_d'Or); Dembélé's article: 'His performances earned him the 2025 Ballon d'Or'."),
    ("2025-09", "non_reform", "Sau làn sóng biểu tình của giới trẻ (Gen Z) tháng 9/2025, ai trở thành Thủ tướng lâm thời Nepal?",
     "Sushila Karki", ["Balen Shah", "K. P. Sharma Oli", "Pushpa Kamal Dahal"],
     W + "Sushila_Karki", "Interim PM 2025-2026 after the September 2025 youth protests; first female PM of Nepal. Balen Shah (RSP PM candidate 2026) is a trap."),
    # ------------------------------------------------------------------ 2025-10
    ("2025-10", "non_reform", "Tháng 10/2025, ai trở thành nữ Thủ tướng đầu tiên của Nhật Bản?",
     "Takaichi Sanae", ["Koike Yuriko", "Kamikawa Yōko", "Noda Seiko"],
     W + "Sanae_Takaichi", "PM and LDP president since Oct 2025 (PM from 21 Oct 2025), first woman in either post."),
    ("2025-10", "non_reform", "Giải Nobel Hòa bình năm 2025 được trao cho ai?",
     "María Corina Machado", ["Donald Trump", "Yulia Navalnaya", "Tổ chức Bác sĩ Không biên giới (MSF)"],
     W + "2025_Nobel_Peace_Prize", "Announced 10 Oct 2025: María Corina Machado of Venezuela."),
    ("2025-10", "non_reform", "Giải Nobel Văn học năm 2025 được trao cho nhà văn nào?",
     "László Krasznahorkai", ["Tàn Tuyết (Can Xue)", "Haruki Murakami", "Gerald Murnane"],
     W + "2025_Nobel_Prize_in_Literature", "Hungarian novelist László Krasznahorkai."),
    ("2025-10", "non_reform", "Bão số 11 năm 2025, ảnh hưởng tới miền Bắc Việt Nam đầu tháng 10/2025, có tên quốc tế là gì?",
     "Matmo", ["Bualoi", "Kalmaegi", "Wipha"],
     VW + "Bão_Matmo_(2025)", "'Bão Matmo ... được Việt Nam định danh là Bão số 11 năm 2025 ... đầu tháng 10 năm 2025'."),
    # ------------------------------------------------------------------ 2025-11
    ("2025-11", "non_reform", "Ai đắc cử Thị trưởng thành phố New York trong cuộc bầu cử ngày 4/11/2025?",
     "Zohran Mamdani", ["Andrew Cuomo", "Eric Adams", "Curtis Sliwa"],
     W + "2025_New_York_City_mayoral_election", "Mamdani won with 50.78%."),
    ("2025-11", "non_reform", "Hoa hậu Hoàn vũ (Miss Universe) 2025, tổ chức tháng 11/2025 tại Thái Lan, thuộc về thí sinh của quốc gia nào?",
     "Mexico", ["Thái Lan", "Venezuela", "Philippines"],
     W + "Miss_Universe_2025", "21 Nov 2025: Fátima Bosch of Mexico crowned."),
    ("2025-11", "non_reform", "Cuối tháng 11/2025, vụ cháy một khu chung cư cao tầng đang sửa chữa làm 168 người thiệt mạng xảy ra ở đâu?",
     "Hồng Kông", ["Seoul (Hàn Quốc)", "Bangkok (Thái Lan)", "Manila (Philippines)"],
     W + "Wang_Fuk_Court_fire", "26 Nov 2025, Wang Fuk Court, Tai Po District, Hong Kong; 168 dead (complex name omitted from the question: it would reveal Hong Kong)."),
    ("2025-11", "non_reform",
     "Bão số 13 năm 2025, đổ bộ vào Gia Lai – Đắk Lắk đầu tháng 11/2025, có tên quốc tế là gì?",
     "Kalmaegi", ["Bualoi", "Fung-wong", "Matmo"],
     VW + "Bão_Kalmaegi_(2025)", "'được Việt Nam định danh là Bão số 13 năm 2025 ... Tối 6 tháng 11, bão đổ bộ vào tỉnh Gia Lai và tỉnh Đắk Lắk'."),
    # ------------------------------------------------------------------ 2025-12
    ("2025-12", "non_reform", "Trận chung kết bóng đá nam SEA Games 33 (tháng 12/2025, tại Thái Lan) kết thúc thế nào?",
     "U22 Việt Nam thắng U22 Thái Lan 3–2 sau hiệp phụ",
     ["U22 Thái Lan thắng U22 Việt Nam 2–1", "U22 Việt Nam thắng U22 Indonesia 1–0", "U22 Indonesia thắng U22 Thái Lan 3–2"],
     W + "Football_at_the_2025_SEA_Games_–_Men's_tournament_final",
     "18 Dec 2025, Rajamangala Stadium: 'Vietnam won the match 3-2 after extra time'. 'VN 1-0 Indonesia' = ASEAN U-23 final Jul 2025 (trap)."),
    ("2025-12", "non_reform", "Ai thắng cuộc bầu cử tổng thống Chile vòng hai ngày 14/12/2025?",
     "José Antonio Kast", ["Jeannette Jara", "Evelyn Matthei", "Johannes Kaiser"],
     W + "2025_Chilean_general_election", "Kast defeated Jara in the 14 Dec run-off with 58%."),
    ("2025-12", "non_reform", "Ngày 14/12/2025, vụ xả súng nhằm vào lễ Hanukkah làm 15 người thiệt mạng xảy ra ở đâu?",
     "Bãi biển Bondi, Sydney (Úc)", ["Manchester (Anh)", "Washington, D.C. (Mỹ)", "Berlin (Đức)"],
     W + "Bondi_Beach_shooting", "14 Dec 2025, Archer Park area of Bondi Beach, Sydney; 15 killed."),
    # ------------------------------------------------------------------ 2026-01
    ("2026-01", "non_reform", "Ngày 3/1/2026, điều gì đã xảy ra với Tổng thống Venezuela Nicolás Maduro?",
     "Bị lực lượng Mỹ bắt giữ và đưa sang Mỹ", ["Từ chức và sang Cuba sống lưu vong",
                                                 "Tuyên thệ nhậm chức nhiệm kỳ thứ ba", "Bị ám sát tại Caracas"],
     W + "2026_United_States_intervention_in_Venezuela", "'On 3 January 2026, the United States launched a military strike in Venezuela and captured ... Maduro'. Third-term inauguration was Jan 2025 (trap)."),
    ("2026-01", "non_reform", "Đại hội XIV của Đảng Cộng sản Việt Nam (tháng 1/2026) bầu ai làm Tổng Bí thư?",
     "Tô Lâm", ["Lương Cường", "Phạm Minh Chính", "Trần Thanh Mẫn"],
     W + "14th_National_Congress_of_the_Communist_Party_of_Vietnam", "Held 19-23 Jan 2026; 'Tô Lâm remained General Secretary'. Caveat: the incumbent is the prior-favoured answer, so this item is weakly informative."),
    ("2026-01", "non_reform", "Trong trận chung kết Giải U23 châu Á 2026 (tại Ả Rập Xê Út), U23 Nhật Bản đã đánh bại đội nào để bảo vệ ngôi vô địch?",
     "U23 Trung Quốc", ["U23 Việt Nam", "U23 Hàn Quốc", "U23 Uzbekistan"],
     W + "2026_AFC_U-23_Asian_Cup", "6-24 Jan 2026: 'Defending champions Japan successfully retained the title after defeating the surprise of the tournament, China, in the final'."),
    ("2026-01", "non_reform", "Ai vô địch nội dung đơn nữ Giải quần vợt Úc Mở rộng 2026?",
     "Elena Rybakina", ["Aryna Sabalenka", "Madison Keys", "Iga Świątek"],
     W + "2026_Australian_Open_–_Women's_singles", "Rybakina beat Sabalenka 6-4 4-6 6-4 in the final (end of Jan 2026)."),
    # ------------------------------------------------------------------ 2026-02
    ("2026-02", "non_reform", "Đội nào vô địch Super Bowl LX (tháng 2/2026)?",
     "Seattle Seahawks", ["New England Patriots", "Kansas City Chiefs", "Philadelphia Eagles"],
     W + "Super_Bowl_LX", "8 Feb 2026: Seahawks beat Patriots 29-13."),
    ("2026-02", "non_reform", "Đảng nào giành chiến thắng áp đảo trong tổng tuyển cử Bangladesh ngày 12/2/2026?",
     "Đảng Dân tộc chủ nghĩa Bangladesh (BNP)", ["Liên đoàn Awami", "Jamaat-e-Islami", "Đảng Công dân Quốc gia (NCP)"],
     W + "2026_Bangladeshi_general_election", "BNP led by Tarique Rahman won two-thirds of seats; Awami League was banned (trap)."),
    ("2026-02", "non_reform", "Ai thắng cuộc bầu cử tổng thống Bồ Đào Nha vòng hai ngày 8/2/2026?",
     "António José Seguro", ["André Ventura", "Henrique Gouveia e Melo", "Luís Marques Mendes"],
     W + "2026_Portuguese_presidential_election", "'Seguro defeated Ventura by a wide margin on the second round, 67% to 33%'."),
    ("2026-02", "non_reform", "Trong tổng tuyển cử Thái Lan ngày 8/2/2026, đảng nào giành nhiều ghế nhất?",
     "Bhumjaithai", ["Đảng Nhân dân (People's Party)", "Pheu Thai", "Đảng Quốc gia Thống nhất Thái (UTN)"],
     W + "Anutin_Charnvirakul", "Election date from en 2026_Thai_general_election; Anutin article: 'His party [Bhumjaithai] placed first in the 2026 election, winning nearly 200 seats.'"),
    # ------------------------------------------------------------------ 2026-03
    ("2026-03", "non_reform", "Phim nào đoạt giải Oscar cho Phim hay nhất tại lễ trao giải ngày 15/3/2026?",
     "One Battle After Another", ["Sinners", "Hamnet", "Frankenstein"],
     W + "98th_Academy_Awards", "'One Battle After Another won the most awards with six, including Best Picture'."),
    ("2026-03", "non_reform", "Đội tuyển nào vô địch World Baseball Classic 2026 (chung kết ngày 17/3/2026)?",
     "Venezuela", ["Mỹ", "Nhật Bản", "Cộng hòa Dominica"],
     W + "2026_World_Baseball_Classic_championship", "Venezuela beat the USA 3-2, first WBC title."),
    ("2026-03", "non_reform", "Đảng nào giành chiến thắng áp đảo trong tổng tuyển cử Nepal ngày 5/3/2026?",
     "Đảng Rastriya Swatantra (RSP)", ["Đảng Đại hội Nepal (Nepali Congress)", "Đảng CPN-UML", "Đảng CPN (Trung tâm Maoist)"],
     W + "2026_Nepalese_general_election", "RSP (Balen Shah as PM candidate) won a majority."),
    ("2026-03", "non_reform", "Tháng 3/2026, ai được Hội đồng Chuyên gia Iran chọn làm Lãnh tụ Tối cao mới?",
     "Mojtaba Khamenei", ["Hassan Rouhani", "Hassan Khomeini", "Gholam-Hossein Mohseni-Ejei"],
     W + "2026_Iranian_supreme_leader_election", "After Ali Khamenei was killed on 28 Feb 2026, 'Mojtaba Khamenei ... was announced as the new supreme leader on 9 March'."),
    # ------------------------------------------------------------------ reform timeline
    ("2025-02", "reform",
     "Theo Kết luận 127-KL/TW ngày 28/2/2025 của Bộ Chính trị, Ban Bí thư, định hướng sắp xếp đơn vị hành chính là gì?",
     "Sáp nhập một số tỉnh, không tổ chức cấp huyện, tiếp tục sáp nhập cấp xã",
     ["Giữ nguyên số tỉnh, chỉ sáp nhập các huyện có quy mô nhỏ",
      "Chia tách các tỉnh lớn, thành lập thêm thành phố trực thuộc trung ương",
      "Giữ nguyên cấp huyện, bỏ cấp xã"],
     "https://baolaocai.vn/bo-chinh-tri-chi-dao-som-trinh-chu-truong-sap-nhap-mot-so-tinh-tam-dung-dai-hoi-dang-cap-huyen-xa-post398194.html",
     "KL 127-KL/TW (28/2/2025): 'Nghiên cứu định hướng sáp nhập một số đơn vị cấp tỉnh, không tổ chức cấp huyện, sáp nhập một số đơn vị cấp xã; thực hiện mô hình địa phương 2 cấp'. Plan announcement only; numbers came later.",
     "Giữ nguyên số tỉnh, chỉ sáp nhập các huyện có quy mô nhỏ"),
    ("2025-04", "reform",
     "Theo chủ trương được Ban Chấp hành Trung ương thống nhất tại Nghị quyết 60-NQ/TW (12/4/2025), sau sắp xếp cả nước có bao nhiêu đơn vị hành chính cấp tỉnh?",
     "34", ["63", "32", "28"],
     "https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm",
     "NQ 60-NQ/TW: '34 tỉnh, thành phố (28 tỉnh và 6 thành phố trực thuộc Trung ương)'. Distractors: 63 = pre-reform (old_answer); 32 ~ the March 2025 proposal of 'giảm khoảng 50% đơn vị hành chính cấp tỉnh' (thesaigontimes.vn, 11/3/2025); 28 = provinces excluding the 6 cities.",
     "63"),
    ("2025-04", "reform",
     "Theo phương án sắp xếp tỉnh được công bố tháng 4/2025 (và được Quốc hội thông qua tháng 6/2025), tỉnh Bình Dương được hợp nhất như thế nào?",
     "Hợp nhất với TP.HCM và tỉnh Bà Rịa – Vũng Tàu, lấy tên Thành phố Hồ Chí Minh",
     ["Hợp nhất với tỉnh Bình Phước, lấy tên tỉnh Bình Dương",
      "Hợp nhất với tỉnh Đồng Nai, lấy tên tỉnh Đồng Nai",
      "Không sáp nhập, giữ nguyên là tỉnh Bình Dương"],
     "https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm",
     "NQ 60 list item 16: 'Hợp nhất tỉnh Bà Rịa - Vũng Tàu, tỉnh Bình Dương và Thành phố Hồ Chí Minh; lấy tên là Thành phố Hồ Chí Minh'. Identical in NQ 202/2025/QH15 and data/processed/provinces_new.jsonl.",
     "Không sáp nhập, giữ nguyên là tỉnh Bình Dương"),
    ("2025-04", "reform", "Tỉnh nào sau đây KHÔNG phải sáp nhập với tỉnh khác trong đợt sắp xếp đơn vị hành chính năm 2025?",
     "Nghệ An", ["Hà Giang", "Quảng Bình", "Bình Phước"],
     "https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm",
     "11 units kept (NQ 60 and NQ 202): Hà Nội, Huế, Lai Châu, Điện Biên, Sơn La, Lạng Sơn, Quảng Ninh, Thanh Hóa, Nghệ An, Hà Tĩnh, Cao Bằng. Hà Giang->Tuyên Quang, Quảng Bình->Quảng Trị, Bình Phước->Đồng Nai. Caveat: a model can pick the largest province by prior (Nghệ An is the largest by area)."),
    ("2025-04", "reform",
     "Theo phương án sắp xếp năm 2025, trung tâm chính trị – hành chính của tỉnh Lào Cai mới (hợp nhất Lào Cai và Yên Bái) đặt ở đâu?",
     "Tại tỉnh Yên Bái cũ", ["Tại tỉnh Lào Cai cũ", "Tại thị xã Sa Pa", "Tại tỉnh Hà Giang cũ"],
     "https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm",
     "NQ 60 list item 2: 'Hợp nhất tỉnh Lào Cai và tỉnh Yên Bái, lấy tên là tỉnh Lào Cai, trung tâm chính trị - hành chính đặt tại tỉnh Yên Bái hiện nay'. Counter-intuitive (name != seat), so not guessable from the name; provinces_new seat_old_province_code=15 (Yên Bái) agrees.",
     "Tại tỉnh Lào Cai cũ"),
    ("2025-06", "reform", "Ngày 12/6/2025, Quốc hội Việt Nam thông qua Nghị quyết 202/2025/QH15 về nội dung gì?",
     "Sắp xếp đơn vị hành chính cấp tỉnh (cả nước còn 34 tỉnh, thành phố)",
     ["Sửa đổi, bổ sung một số điều của Hiến pháp năm 2013",
      "Sắp xếp đơn vị hành chính cấp xã của 34 tỉnh, thành phố",
      "Thành lập thành phố Huế trực thuộc trung ương"],
     "https://luatvietnam.vn/hanh-chinh/nghi-quyet-202-2025-qh15-cua-quoc-hoi-ve-viec-sap-xep-don-vi-hanh-chinh-cap-tinh-402728-d1.html",
     "NQ 202/2025/QH15, passed 12/6/2025, in force on passage: 34 provincial units (28 tỉnh + 6 thành phố). Traps: NQ 203/2025/QH15 (constitution, 16/6/2025), UBTVQH commune resolutions (16/6/2025), NQ 175/2024/QH15 (Huế)."),
    ("2025-06", "reform",
     "Sau đợt sắp xếp năm 2025 (Ủy ban Thường vụ Quốc hội quyết định tháng 6/2025), cả nước có bao nhiêu đơn vị hành chính cấp xã?",
     "3.321", ["10.035", "Khoảng 5.000", "2.500"],
     "https://www.vietnamplus.vn/uy-ban-thuong-vu-quoc-hoi-ca-nuoc-con-3321-don-vi-hanh-chinh-cap-xa-post1042624.vnp",
     "16/6/2025: 3.321 (2.621 xã, 687 phường, 13 đặc khu), down from 10.035 (old_answer). 'Khoảng 5.000' = the ~50% target of Kết luận 137-KL/TW (28/3/2025); NQ 60 (12/4/2025) then raised the target to a 60-70% reduction. NB: a May 2025 draft already totalled 3.321 but with 2.636 xã / 672 phường (vietnamplus related link, 11/05/2025).",
     "10.035"),
    ("2025-06", "reform",
     "Mô hình chính quyền địa phương 2 cấp và 34 tỉnh, thành phố mới ở Việt Nam chính thức hoạt động từ ngày nào?",
     "01/7/2025", ["01/9/2025", "01/01/2026", "30/4/2025"],
     "https://luatvietnam.vn/hanh-chinh/nghi-quyet-202-2025-qh15-cua-quoc-hoi-ve-viec-sap-xep-don-vi-hanh-chinh-cap-tinh-402728-d1.html",
     "NQ 202 Art. 2(2): 'chính thức hoạt động từ ngày 01 tháng 7 năm 2025'. Month = 2025-06: NQ 60 (12/4/2025) already ended the district level from 01/7/2025, but the merged PROVINCES were then planned to start on 01/9/2025 (Home Affairs Minister: provincial mergers 'before August 30 ... starting from September 1', en.wikipedia 2025_Vietnamese_administrative_reforms; PM's 11 Mar 2025 timeline likewise). NQ 202 (June) moved them to 01/7/2025. So '01/9/2025' is the announce-era answer."),
    ("2025-07", "reform", "Hiện nay, chính quyền địa phương ở Việt Nam được tổ chức theo mô hình nào?",
     "Hai cấp: cấp tỉnh và cấp xã (không còn cấp huyện)",
     ["Ba cấp: tỉnh, huyện, xã", "Hai cấp: cấp tỉnh và cấp huyện (bỏ cấp xã)", "Bốn cấp: tỉnh, huyện, xã, thôn"],
     "https://pbgdpl.cantho.gov.vn/nghi-quyet-sua-doi-bo-sung-mot-so-dieu-cua-hien-phap-nuoc-cong-hoa-xa-hoi-chu-nghia-viet-nam",
     "NQ 203/2025/QH15 (Constitution amendment, 16/6/2025): 'Kết thúc hoạt động của đơn vị hành chính cấp huyện trong cả nước từ ngày 01/7/2025'. Month = 2025-07 (in force); the plan itself was public from NQ 60-NQ/TW (12/4/2025: 'kết thúc hoạt động của đơn vị hành chính cấp huyện từ ngày 01/7/2025'), so an announce-era model that assumes the plan was carried out can answer correctly. Old structure = 3 levels (old_answer).",
     "Ba cấp: tỉnh, huyện, xã"),
]

# ---------------------------------------------------------------------- headline (short answer)
NQ60 = "https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm"
NQ202 = "https://luatvietnam.vn/hanh-chinh/nghi-quyet-202-2025-qh15-cua-quoc-hoi-ve-viec-sap-xep-don-vi-hanh-chinh-cap-tinh-402728-d1.html"
HEADLINE: list[dict] = [
    dict(question="Việt Nam hiện có bao nhiêu đơn vị hành chính cấp tỉnh (tỉnh và thành phố trực thuộc trung ương)?",
         answer="34", answer_aliases=[], old_answer="63", month="2025-06", source_url=NQ202,
         notes="NQ 202/2025/QH15: 34 (28 tỉnh + 6 thành phố). Still 34 as of 2026-10 although some provinces became centrally-run cities in 2026."),
    dict(question="Việt Nam hiện có bao nhiêu đơn vị hành chính cấp xã (gồm xã, phường và đặc khu)?",
         answer="3321", answer_aliases=["3.321", "3,321"], old_answer=["10035", "10.035", "10,035"], month="2025-06",
         source_url="https://www.vietnamplus.vn/uy-ban-thuong-vu-quoc-hoi-ca-nuoc-con-3321-don-vi-hanh-chinh-cap-xa-post1042624.vnp",
         notes="3.321 = 2.621 xã + 687 phường + 13 đặc khu (UBTVQH, 16/6/2025); old 10.035."),
    dict(question="Chính quyền địa phương ở Việt Nam hiện được tổ chức theo mô hình mấy cấp?",
         answer="2", answer_aliases=[], old_answer="3", month="2025-07",
         source_url="https://pbgdpl.cantho.gov.vn/nghi-quyet-sua-doi-bo-sung-mot-so-dieu-cua-hien-phap-nuoc-cong-hoa-xa-hoi-chu-nghia-viet-nam",
         notes="District level ended 1/7/2025 (NQ 203/2025/QH15)."),
    dict(question="Tỉnh Bình Dương trước đây nay thuộc đơn vị hành chính cấp tỉnh nào?",
         answer="Thành phố Hồ Chí Minh", answer_aliases=[], old_answer="Tỉnh Bình Dương", month="2025-06", source_url=NQ60,
         notes="Bà Rịa - Vũng Tàu + Bình Dương + TP.HCM -> Thành phố Hồ Chí Minh (NQ 60 list, NQ 202)."),
    dict(question="Tỉnh Hà Giang trước đây nay thuộc tỉnh nào?",
         answer="Tỉnh Tuyên Quang", answer_aliases=[], old_answer="Tỉnh Hà Giang", month="2025-06", source_url=NQ60,
         notes="Tuyên Quang + Hà Giang -> Tỉnh Tuyên Quang."),
    dict(question="Tỉnh Quảng Nam trước đây nay thuộc đơn vị hành chính cấp tỉnh nào?",
         answer="Thành phố Đà Nẵng", answer_aliases=[], old_answer="Tỉnh Quảng Nam", month="2025-06", source_url=NQ60,
         notes="Quảng Nam + Đà Nẵng -> Thành phố Đà Nẵng."),
    dict(question="Tỉnh Kon Tum trước đây nay thuộc tỉnh nào?",
         answer="Tỉnh Quảng Ngãi", answer_aliases=[], old_answer="Tỉnh Kon Tum", month="2025-06", source_url=NQ60,
         notes="Kon Tum + Quảng Ngãi -> Tỉnh Quảng Ngãi (a highland province joined to a coastal one; not guessable by adjacency alone, Gia Lai is the tempting wrong answer)."),
    dict(question="Tỉnh Đắk Nông trước đây nay thuộc tỉnh nào?",
         answer="Tỉnh Lâm Đồng", answer_aliases=[], old_answer="Tỉnh Đắk Nông", month="2025-06", source_url=NQ60,
         notes="Lâm Đồng + Đắk Nông + Bình Thuận -> Tỉnh Lâm Đồng (Đắk Lắk is the tempting wrong answer)."),
]


def nfc(s):
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else s


def shuffle_choices(item_id: str, correct: str, distractors: list[str]) -> tuple[list[str], str]:
    opts = [correct, *distractors]
    assert len(opts) == 4 and len(set(opts)) == 4, (item_id, opts)
    random.Random(f"{SEED}:{item_id}").shuffle(opts)
    return opts, LETTERS[opts.index(correct)]


def build_probe_items() -> list[dict]:
    items, per_month = [], {}
    for row in RAW:
        month, topic, q, correct, distractors, url, notes = row[:7]
        old = row[7] if len(row) > 7 else None
        if month < "2024-09":
            per_month["anchor"] = per_month.get("anchor", 0) + 1
            iid = f"probe-anchor-{per_month['anchor']:02d}"
        else:
            key = (month, topic)
            per_month[key] = per_month.get(key, 0) + 1
            iid = f"probe-{month}-{'r' if topic == 'reform' else 'n'}{per_month[key]:02d}"
        choices, ans = shuffle_choices(iid, nfc(correct), [nfc(d) for d in distractors])
        items.append({
            "id": iid, "month": month, "topic": topic, "question": nfc(q), "choices": choices,
            "answer": ans, "source_url": url, "notes": nfc(notes),
            "qtype": "P_cutoff", "format": "mcq", "answer_aliases": [],
            "old_answer": nfc(old), "meta": {"anchor": month < "2024-09"},
        })
    items.sort(key=lambda it: (it["month"], it["topic"], it["id"]))
    return items


def build_headline() -> list[dict]:
    out = []
    for i, h in enumerate(HEADLINE, 1):
        out.append({
            "id": f"headline-{i:02d}", "qtype": "T0_headline", "question": nfc(h["question"]),
            "format": "short", "choices": None, "answer": nfc(h["answer"]),
            "answer_aliases": [nfc(a) for a in h["answer_aliases"]],
            "old_answer": [nfc(o) for o in h["old_answer"]] if isinstance(h["old_answer"], list) else nfc(h["old_answer"]),
            "month": h["month"], "topic": "reform", "source_url": h["source_url"], "notes": nfc(h["notes"]),
            "meta": {"province_changed": None, "ward_changed": None, "has_diacritics": True},
        })
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    items = build_probe_items()
    head = build_headline()
    write_jsonl(OUT_DIR / "probe_items.jsonl", items)
    write_jsonl(OUT_DIR / "headline_probe.jsonl", head)
    write_jsonl(OUT_DIR / "probe_all.jsonl", items + head)  # one file for viadmin.eval.runner --items
    from collections import Counter
    c = Counter(("anchor" if it["meta"]["anchor"] else it["month"], it["topic"]) for it in items)
    print(f"wrote {len(items)} probe items, {len(head)} headline items -> {OUT_DIR}")
    for k in sorted(c):
        print(f"  {k[0]:8s} {k[1]:10s} {c[k]}")
    print("answer letters:", dict(sorted(Counter(it["answer"] for it in items).items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
