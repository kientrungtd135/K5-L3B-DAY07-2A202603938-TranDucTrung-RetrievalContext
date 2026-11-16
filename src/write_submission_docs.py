"""Build submission documentation from saved results; no API calls."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = "report/individual/2A202603938_TranDucTrung.md"
DAY6 = "https://github.com/kientrungtd135/K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion"
PIN = "7aa3adc7a0bf794daa654156b06bf9743403b763"

def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))

def cell(value):
    return ("N/A" if value is None else str(value)).replace("|", "\\|").replace("\n", " ")

def table(headers, rows):
    return "\n".join(
        ["| " + " | ".join(headers) + " |",
         "| " + " | ".join(["---"] * len(headers)) + " |"]
        + ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    ) + "\n"

def frac(v):
    return (
        f"{v['n']}/{v['N']} ({100*v['n']/v['N']:.1f}%)"
        if v["N"] else "0/0 (N/A)"
    )

def number(v):
    return "N/A" if v is None else f"{v:,.2f}"

def main():
    summary = read("results/submission_summary.json")
    frozen = read("configs/final_selection.json")
    manifest = read("benchmark/manifest.json")
    cards = summary["profiles"]

    report = ["""# Báo cáo cá nhân Day 7 — Retrieval & Context Engineering

- Họ tên: Trần Đức Trung; MSSV: 2A202603938; lớp: L3B.
- Phạm vi: phần cơ bản; không thực hiện bonus tài liệu từ 100 trang.
- AI hỗ trợ lập trình, thiết kế benchmark và đề xuất chấm sau khi đọc evidence. Tất cả nhãn hiện là `ai_proposed`, chưa được xác nhận độc lập bởi người chấm.

## 1. Dữ liệu, model và benchmark

Kế thừa index B Day 6: 30 bài Markdown, gồm 15 business và 15 technology; chunk theo đoạn với max_size=500 ký tự, tổng cộng 701 chunk. page=1 là đơn vị bài viết, không phải trang PDF.

Vector store: PostgreSQL 16 + pgvector 0.8.7, bảng public.day6_chunks, strategy B, tìm kiếm cosine exact. Embedding: text-embedding-3-small, 1536 chiều. Agent thật: deepseek-v4.1-flash qua API tương thích OpenAI tại https://api.xah.io/v1. Model ID là alias provider, không bảo đảm snapshot bất biến.

Môi trường đã chạy: Windows, Python 3.13.3; openai 2.54.0, psycopg 3.3.8, python-dotenv 1.2.4, rank-bm25 0.2.2, numpy 2.5.5, pypdf 6.21.4. Các dependency được pin trong requirements.txt.

Benchmark gồm 24 câu: dev có 15 câu có đáp án + 2 câu thiếu evidence; test có 5 câu có đáp án mới + 2 câu thiếu evidence. Dev tái sử dụng câu hỏi dev Day 6. Năm câu test có đáp án dùng nguồn khác các nguồn câu hỏi Day 6. Cả 20 gold quote đều nằm trọn trong chunk B đúng source/page. Agent chỉ nhận câu hỏi và filter được cung cấp, không nhận expected answer, gold hoặc absence reason.

Bốn câu thiếu evidence hỏi về tỷ trọng doanh số Ripple Rug năm 2022, lợi nhuận sau thuế Betashares FY2023, giá thuê bao Mozilla.social và phán quyết bồi thường Helena World Chronicle. Lý do và dấu vết tìm kiếm nằm trong benchmark/absence_audit.json. AI đối chiếu nguồn liên quan và tìm trong corpus; không kết luận thiếu dữ liệu chỉ từ top-k. Nhãn absence chưa có xác nhận độc lập.

Nguồn dữ liệu là subset MultiHopRAG, dataset khai báo ODC-BY. URL/attribution được giữ trong manifest và trace. License dataset không xác nhận riêng quyền phân phối từng bài báo. Day 7 cung cấp nguồn Day 6 và cách tái tạo; trace vẫn chứa các đoạn nguồn đã dùng.
"""]
    report.append(
        f"\nNguồn Day 6: [{PIN[:12]}]({DAY6}/tree/{PIN}); "
        "manifest tại starter/data/manifest.json trong repo đó.\n"
        f"\nFingerprint corpus B: `{manifest['corpus_sha256']}`.\n"
        f"\nChốt cấu hình lúc `{frozen['frozen_at_utc']}`; xem "
        "[final_selection.json](../../configs/final_selection.json).\n"
    )

    report.append("\n## 2. Phương pháp và cấu hình\n\n")
    report.append(table(
        ["Profile", "Thay đổi / giả thuyết", "Search tối đa"],
        [
            ["dense_baseline", "Dense exact cosine trên vector Day 6", 1],
            ["bm25_candidate", "Khớp tên riêng/từ khóa, giảm độ trễ", 1],
            ["hybrid_candidate", "Kết hợp lexical và semantic để bổ sung evidence", 1],
            ["auto_candidate", "Model chọn tool và viết lại query, tìm bổ sung", 3],
            ["auto_english_v2", "Auto + prompt ngắn, guard CJK/citation abstention", 3],
        ]
    ))
    report.append("""
Mọi profile: top-k=3, context budget=4000 ký tự gồm ID/URL/vị trí/text, temperature=0, max output=1024 token. Chỉ dùng category filter do câu hỏi cung cấp, không suy ra từ gold. BM25 dùng NFC/casefold, regex \\w+, k1=1.5, b=0.75. Hybrid lấy tối đa 10 candidate mỗi nhánh rồi RRF với hằng số 60; không cộng trực tiếp hai loại score. Không dùng reranker.

Agent có search_dense, search_bm25, search_hybrid và finish_answer; profile đơn phương pháp chỉ có search tool tương ứng. Context tích lũy ưu tiên kết quả mới, khử trùng ID và giữ nguyên chunk vừa budget. Tool output cũ được thay bằng thông báo dùng context mới nhất. Khi hết lượt search, buộc finish; model turn tối đa bằng max_searches+4. Lỗi API/database được ghi thành error, không thay bằng abstain giả.

Validator kiểm tra citation thuộc context và khớp inline/list. V2 thêm chặn CJK và cấm citation cả inline lẫn list khi abstain. Guard không tự chứng minh semantic support và không phải bộ nhận diện đầy đủ mọi ngôn ngữ.

## 3. Retrieval với query gốc

Hit@1/Hit@3 đếm câu có gold evidence đúng source/page trong top-1/top-3, chia số câu có đáp án. Exact context match kiểm tra gold còn trong context sau packing. Đây là query gốc, tách khỏi query model viết lại.

Dev latency tính trên 17 query thành công; test trên 5 câu có đáp án. Câu thiếu evidence không nằm trong mẫu số hit/context.

""")
    raw_rows = []
    for split in ("dev", "test"):
        for method, m in summary["raw_retrieval_" + split].items():
            def hit(key):
                value = m[key]
                return frac(
                    value if isinstance(value, dict)
                    else {"n": value, "N": m["N"]}
                )
            raw_rows.append([
                split, method, hit("hit1"), hit("hit3"),
                hit("context_match"), number(m["median_ms"]), m["errors"]
            ])
    report.append(table(
        ["Split", "Method", "Hit@1", "Hit@3", "Context match", "Median ms", "Errors"],
        raw_rows
    ))

    report.append("""
## 4. Agent: context, câu trả lời và citation

Grounded: 0=sai/thiếu evidence hoặc từ chối nhầm; 1=đúng một phần; 2=đúng và đủ. Context: 0=không có evidence; 1=thiếu điều kiện/nguồn; 2=đủ. Context Evidence Rate là số câu context mức 2 / số câu có đáp án.

Citation phải thuộc context và hỗ trợ câu trả lời; đếm ID duy nhất mỗi câu, gồm cả inline ID không có trong list. Lỗi ngôn ngữ báo riêng với factual grade.

""")
    quality, operations, ranking, costs, distributions = [], [], [], [], []
    for c in cards:
        m, u = c["metrics"], c["usage"]
        g = m["grounded_answer"]
        quality.append([
            c["split"], c["profile"],
            f"{g['0']}/{g['1']}/{g['2']}", f"{g['mean']:.3f}/2",
            frac(m["context_evidence"]), frac(m["citation_validity"]),
            frac(m["abstention"]), frac(m["false_abstention"])
        ])
        operations.append([
            c["split"], c["profile"], frac(m["tool_use"]),
            frac(m["answer_citation_coverage"]), m["language_errors"],
            m["citation_format_errors"], number(m["median_ms"]),
            m["provider_errors"]
        ])
        automatic = read(
            f"results/{c['run']}/automatic_summary.json"
        )["profiles"][c["profile"]]
        ranking.append([
            c["split"], c["profile"],
            frac(automatic["first_search_hit1"]),
            frac(automatic["first_search_hit3"])
        ])
        costs.append([
            c["split"], c["profile"], u["model_sdk_calls"],
            u["search_calls"], u["embedding_calls_with_trace"],
            u["model"]["total_tokens"], u["embedding"]["total_tokens"],
            number(u["model"]["provider_cost_raw"]),
            number(u["embedding"]["provider_cost_raw"])
        ])
        distributions.append([
            c["split"], c["profile"],
            json.dumps(m["model_call_distribution"]),
            json.dumps(m["search_call_distribution"]),
            u["format_repairs"], u["non_tool_model_turns"]
        ])

    report.append(table(
        ["Split", "Profile", "Số mức 0/1/2", "Mean", "Context đủ",
         "Citation hợp lệ", "Abstention đúng", "Từ chối nhầm"],
        quality
    ))
    report.append("\n")
    report.append(table(
        ["Split", "Profile", "Tool use", "Câu có citation",
         "Lỗi ngôn ngữ", "Lỗi inline/list", "Median ms", "Errors"],
        operations
    ))
    report.append(
        "\nRanking lượt search đầu với query model viết lại "
        "(khác bảng query gốc):\n\n"
    )
    report.append(table(
        ["Split", "Profile", "First Hit@1", "First Hit@3"], ranking
    ))

    report.append("""
## 5. Lỗi dev, thay đổi và lựa chọn trước test

1. **d7-dev-q09 — từ chối nhầm.** Query gốc dense có evidence newsletter tại rank 2, nhưng query baseline do model viết lại lấy các đoạn podcast ở doc_0012, thiếu lịch newsletter ở doc_0010. Một search không khôi phục được evidence: grounded/context 0. Auto bổ sung search; v2 trả lời đúng Thursday 12 p.m. PT, grounded/context 2. Query gốc tốt không bảo đảm query viết lại tốt.

2. **d7-dev-q13 — thêm chi tiết thiếu evidence.** Dense/BM25/hybrid trả lời đúng phần API nhưng hoàn tất thêm ý wireless-carrier từ câu bị cắt mà chưa có continuation trong context. Chấm bảo thủ grounded 1, citation chưa hỗ trợ toàn bộ câu. Auto v1 có các đoạn bổ sung nên được 2; v2 chỉ trả lời phần hỏi và được 2. Exact gold match không có nghĩa toàn bộ câu đều được hỗ trợ.

3. **Ngôn ngữ và citation khi abstain.** V1 có 2/4/2 lỗi ngôn ngữ ở dense/BM25/hybrid. Hybrid dev-u02 có inline citation nhưng list rỗng: citation hỗ trợ nguồn vẫn tính vào denominator, đồng thời báo một lỗi format. V2 thêm guard/prompt và sáu regression tests. Hai repair v2 dev là sửa citation ở q03/q07, không phải sửa ngôn ngữ.

BM25 và hybrid là hai cấu hình thử cải thiện, đồng thời là hai phương pháp retrieval mới. Auto và v2 là các thử nghiệm tiếp theo. Tiêu chí ban đầu: mean grounded cao nhất, rồi context, citation, latency. Trong dev, chính sách được điều chỉnh ưu tiên implementation có guard ngôn ngữ/citation abstention; thay đổi và lý do được ghi trong final_selection trước test.

Auto v1 cũng đạt 30/30 điểm dev và nhanh hơn v2. Nếu chỉ dùng tiêu chí điểm và latency ban đầu, Auto v1 sẽ được ưu tiên. V2 được chọn vì guard ở mức code cùng prompt hạn chế phát biểu thêm, chấp nhận latency cao hơn; không tuyên bố v2 tăng factual accuracy dev so với Auto v1. Guard v1 vẫn có lỗ hổng dù các output Auto v1 quan sát được đều đạt.

Test chỉ chạy sau freeze; không sửa prompt/parameter theo lỗi test hoặc chạy lại câu thành công để chọn kết quả đẹp. Test-02 baseline từ chối nhầm vì query viết lại không tìm được counts, còn v2 tìm đủ evidence. Test-03 v2 cần 6 model calls, 2 searches và 2 citation repairs; giữ nguyên trong trace.

Dense query gốc test đạt 5/5, BM25/hybrid đạt 4/5; không kết luận hybrid luôn tốt hơn dense.

## 6. Lượt gọi, token và chi phí

Đơn vị thời gian ms. Median agent tính trên toàn bộ 17 dev hoặc 7 test thành công, không gồm khởi tạo retriever và ghi file; có độ trễ API/network. Model call là SDK call, không thấy retry HTTP nội bộ.

Bảng gồm cả câu thiếu evidence. Token/chi phí lấy từ usage đã lưu. Chi phí là x_ckey.cost thô do provider trả về, chưa xác minh đơn vị hoặc đối soát hóa đơn; không quy đổi USD. BM25 không gọi embedding nên ghi 0 lượt, token/phí embedding N/A.

""")
    report.append(table(
        ["Split", "Profile", "Model calls", "Search calls", "Embed calls",
         "Model tokens", "Embed tokens", "Model cost raw", "Embed cost raw"],
        costs
    ))
    report.append(
        "\nPhân bố dạng số_lượt:số_câu. Non-tool turn là response không có "
        "tool call, phân biệt với citation repair:\n\n"
    )
    report.append(table(
        ["Split", "Profile", "Model calls", "Search calls", "Repairs", "Non-tool turns"],
        distributions
    ))
    report.append("\nChi phí query gốc tính riêng, không cộng lặp vào agent:\n\n")
    report.append(table(
        ["Split/method", "Embed calls", "Embed tokens", "Embed cost raw"],
        [
            [name, u["embedding_calls_with_trace"],
             u["embedding"]["total_tokens"],
             number(u["embedding"]["provider_cost_raw"])]
            for name, u in summary["original_query_usage"].items()
        ]
    ))
    report.append("""
Coverage usage/token/cost response xem [submission_summary.json](../../results/submission_summary.json). Tổng hợp không bao gồm smoke checks đã bỏ và phí tạo index Day 6; không phải tổng hóa đơn toàn buổi. Không có system error hay failed attempt trong các run được nộp.

## 7. Đối chiếu từng câu test

""")
    labels = {
        (r["profile_id"], r["query_id"]): r
        for r in read("results/agent_test_final/reviews.json")
    }
    case_rows = []
    for case in read("benchmark/test.json"):
        for profile in ("dense_baseline", "auto_english_v2"):
            trace = read(
                f"results/agent_test_final/{profile}/{case['id']}.json"
            )
            label = labels[(profile, case["id"])]
            answer = re.sub(
                r"\[by_paragraph-[^\]]+\]", "", trace["answer"]
            ).strip()
            target = (
                f"../../results/agent_test_final/{profile}/{case['id']}.json"
            )
            case_rows.append([
                case["id"], profile, case["question"], answer,
                label["answer_grade"], label["context_grade"],
                label["reason"], f"[trace/citations]({target})"
            ])
    report.append(table(
        ["Query", "Profile", "Câu hỏi", "Câu trả lời",
         "Grounded", "Context", "Lý do", "Evidence"],
        case_rows
    ))
    report.append("""
N/A ở câu thiếu evidence nghĩa là grounded/context không áp dụng; chấm riêng abstention. Nhãn từng câu và SHA trace nằm trong reviews.json của agent_dev_v1, agent_dev_v2 và agent_test_final. Trace giữ tool call, query, candidates, context, answer, citation, usage và lỗi.

## 8. Giới hạn và kết luận

V2 giảm một false abstention trên 5 câu test có đáp án, đổi lấy gần gấp đôi median latency và nhiều token/model calls hơn baseline. Perfect score trong mẫu nhỏ không chứng minh khả năng tổng quát. Test được người soạn/AI biết đáp án khi tạo benchmark, không phải đánh giá mù bởi bên độc lập.

Nhãn semantic và absence mới là AI-proposed; người học cần đối chiếu trước khi tự xác nhận. Fixture/mocked unit tests chỉ kiểm tra hành vi code, không thay thế benchmark agent thật. Bộ test code đã chạy 21 tests, OK.

Chưa đánh giá bảng, ảnh, biểu đồ hoặc tài liệu 100 trang, chưa có bonus. Chunk 500 ký tự có thể cắt câu; exact-quote metric không bao quát mọi paraphrase/multi-hop. Hash corpus xác nhận ID/text/source/position, không đóng băng mọi vector/provider snapshot. Temperature=0 không bảo đảm output giống tuyệt đối khi model alias, API hoặc môi trường thay đổi. Retrieved content được coi là dữ liệu không tin cậy, nhưng chưa benchmark prompt injection.
""")
    report_path = ROOT / REPORT
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("".join(report), encoding="utf-8")

    readme = f"""# Day 7 — Agentic Retrieval & Context Engineering

Trần Đức Trung · 2A202603938 · L3B.

Dense/BM25/hybrid trên cùng index Day 6; agent thật có tool calling, citation và abstention.

[Báo cáo cá nhân]({REPORT}) · [Tổng hợp kết quả](results/submission_summary.json) · [Cấu hình đã chốt](configs/final_selection.json) · [Đề bài gốc](https://github.com/VinUni-AI20k/K5-L3-Day07-Retrieval-Context-Engineering).

## Kết quả đã lưu

Test: 5 câu có đáp án + 2 thiếu evidence. Baseline grounded mean 1.6/2, context 4/5, abstention đúng 2/2; v2 mean 2/2, context 5/5, abstention đúng 2/2. Median lần lượt 5.03s và 9.54s. Nhãn là ai_proposed, chưa được xác nhận độc lập bởi người chấm. Chi tiết query gốc, query viết lại, lỗi và chi phí raw trong báo cáo.

## Cài đặt Windows PowerShell

Môi trường đã chạy: Python 3.13.3, Docker Compose và Git. Chạy tại thư mục gốc Day 7:

```powershell
py -3.13 -m venv .venv
& .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) {{ Copy-Item .env.example .env }}
notepad .env

```

Điền API key cá nhân trong .env. AGENT_API_KEY/AGENT_BASE_URL trống thì dùng OPENAI_API_KEY/OPENAI_BASE_URL. DATABASE_URL mẫu dành PostgreSQL local. Không commit .env.

## Dữ liệu và tái tạo index

Nguồn Day 6: [{PIN[:12]}]({DAY6}/tree/{PIN}); manifest tại starter/data/manifest.json. Có 30 bài Markdown, 701 chunk B, embedding text-embedding-3-small 1536 chiều. Dataset MultiHopRAG khai báo ODC-BY; quyền riêng từng bài báo chưa được xác nhận. Giữ URL/attribution. page=1 là article unit.

Nếu đã có database Day 6, khởi động và kiểm tra từ Day 7:

```powershell
docker compose -p day6_student_starter -f "..\\K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion\\starter\\docker-compose.yml" up -d --wait
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.day6_bridge
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.review_dev --diagnostics-only
```

Các lệnh kiểm tra không gọi embedding API. Cần thấy B: 701 chunks, 30 documents, 1536 dimensions; review_dev kiểm tra corpus hash.

Chỉ khi database mới chưa có index: tái tạo bằng DEV Day 6 tại commit được pin. Bước này gọi API và phát sinh phí; không cần chạy TEST Day 6.

```powershell
$Day7Root = (Get-Location).Path
New-Item -ItemType Directory -Force .\\deps | Out-Null
git clone {DAY6}.git .\\deps\\day6
git -C .\\deps\\day6 checkout {PIN}
$Day6Env = Join-Path $Day7Root "deps\\day6\\starter\\.env"
$EnvText = Get-Content -LiteralPath .\\.env -Raw -Encoding UTF8
[System.IO.File]::WriteAllText($Day6Env, $EnvText, [System.Text.UTF8Encoding]::new($false))
Push-Location .\\deps\\day6\\starter
try {{
    docker compose -p day6_student_starter up -d --wait
    & "$Day7Root\\.venv\\Scripts\\python.exe" -X utf8 -m src.run
}} finally {{ Pop-Location }}
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.day6_bridge
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.review_dev --diagnostics-only
```

DEV Day 6 tạo A/B/C; Day 7 chỉ đọc B. deps/ được ignore. Model/API thay đổi có thể làm vector hoặc ranking khác. Không xóa Docker volume chứa index để dọn repo.

## Kiểm tra và tổng hợp, không gọi API

```powershell
& .\\.venv\\Scripts\\python.exe -X utf8 -m unittest discover -s tests -v
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.summarize_results
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.write_submission_docs
```

21 unit tests đã pass, gồm sáu guard tests v2. Unit tests không thay thế benchmark agent thật. Tổng hợp kiểm tra hash pipeline/review; không tự chấm semantic hoặc đổi AI-proposed thành human-confirmed.

## Chạy agent và tái lập thí nghiệm

Các lệnh sau có gọi API, phát sinh phí. Dùng output mới để giữ trace cũ:

```powershell
$RunTag = Get-Date -Format "yyyyMMdd_HHmmss"
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.agent_v2 --method auto --query-id d7-dev-q09 --output ".\\results\\reproduction\\demo_$RunTag.json"
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.evaluate_agent --run-name "reproduce_v1_$RunTag"
& .\\.venv\\Scripts\\python.exe -X utf8 -m src.evaluate_agent_v2 --run-name "reproduce_v2_$RunTag"
```

Tạo benchmark trên workspace mới chưa có benchmark/*.json: `python -X utf8 -m src.prepare_benchmark --day6-root PATH_TO_DAY6`, dùng nguồn Day 6 được pin.

Ranking query gốc dev: `python -X utf8 -m src.evaluate_retrieval`; chạy khi chưa có output hoặc dùng --resume để giữ thành công và retry lỗi.

Luồng gốc: tạo benchmark -> retrieval DEV -> agent v1 DEV -> đọc/chấm -> v2 DEV -> đọc/chấm -> freeze và TEST qua src.final_test -> đọc/chấm TEST -> tổng hợp.

`python -X utf8 -m src.final_test --resume` chỉ dành tiếp tục lỗi hệ thống với pipeline đã đóng băng, giữ câu thành công. Bài hiện đã chạy xong TEST; không chỉnh theo test hoặc xóa trace để chạy lại lấy kết quả tốt hơn. Muốn chọn cấu hình khác cần test độc lập mới.

## Các file chính

- src/: bridge Day 6, retrieval, agent v1/v2, runner, review, tổng hợp và tạo báo cáo.
- benchmark/: 24 câu, evidence, absence audit, fingerprint.
- configs/final_selection.json: cấu hình và hash chốt trước test.
- results/retrieval_dev/: query gốc dev.
- results/agent_test_final/raw_retrieval/: query gốc test.
- results/agent_dev_v1/, agent_dev_v2/, agent_test_final/: trace, plan, automatic summary và review.
- starter/*.py, data/example_*.json, tests/: dependency và fixture kiểm thử.

Chỉ làm phần cơ bản, không có bonus. Provider cost raw chưa xác nhận đơn vị tiền tệ. Tổng hợp không bao gồm smoke checks và tạo index Day 6. Nộp link repo cá nhân có quyền xem; không push vào upstream đề bài.
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")

    ignore = ROOT / ".gitignore"
    text = ignore.read_text(encoding="utf-8-sig")
    for rule in ("deps/", "results/reproduction/", "results/reproduce_*/"):
        if rule not in text.splitlines():
            text += "\n" + rule + "\n"
    ignore.write_text(text, encoding="utf-8")

    print("Saved:", report_path)
    print("Saved:", ROOT / "README.md")
    print("Updated: .gitignore")

if __name__ == "__main__":
    main()
