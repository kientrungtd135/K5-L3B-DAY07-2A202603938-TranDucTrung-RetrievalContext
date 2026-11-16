# Day 7 — Agentic Retrieval & Context Engineering

Trần Đức Trung · 2A202603938 · L3B.

Dense/BM25/hybrid trên cùng index Day 6; agent thật có tool calling, citation và abstention.

[Báo cáo cá nhân](report/individual/2A202603938_TranDucTrung.md) · [Tổng hợp kết quả](results/submission_summary.json) · [Cấu hình đã chốt](configs/final_selection.json) · [Đề bài gốc](https://github.com/VinUni-AI20k/K5-L3-Day07-Retrieval-Context-Engineering).

## Kết quả đã lưu

Test: 5 câu có đáp án + 2 thiếu evidence. Baseline grounded mean 1.6/2, context 4/5, abstention đúng 2/2; v2 mean 2/2, context 5/5, abstention đúng 2/2. Median lần lượt 5.03s và 9.54s. Nhãn là ai_proposed, chưa được xác nhận độc lập bởi người chấm. Chi tiết query gốc, query viết lại, lỗi và chi phí raw trong báo cáo.

## Cài đặt Windows PowerShell

Môi trường đã chạy: Python 3.13.3, Docker Compose và Git. Chạy tại thư mục gốc Day 7:

```powershell
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env

```

Điền API key cá nhân trong .env. AGENT_API_KEY/AGENT_BASE_URL trống thì dùng OPENAI_API_KEY/OPENAI_BASE_URL. DATABASE_URL mẫu dành PostgreSQL local. Không commit .env.

## Dữ liệu và tái tạo index

Nguồn Day 6: [7aa3adc7a0bf](https://github.com/kientrungtd135/K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion/tree/7aa3adc7a0bf794daa654156b06bf9743403b763); manifest tại starter/data/manifest.json. Có 30 bài Markdown, 701 chunk B, embedding text-embedding-3-small 1536 chiều. Dataset MultiHopRAG khai báo ODC-BY; quyền riêng từng bài báo chưa được xác nhận. Giữ URL/attribution. page=1 là article unit.

Nếu đã có database Day 6, khởi động và kiểm tra từ Day 7:

```powershell
docker compose -p day6_student_starter -f "..\K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion\starter\docker-compose.yml" up -d --wait
& .\.venv\Scripts\python.exe -X utf8 -m src.day6_bridge
& .\.venv\Scripts\python.exe -X utf8 -m src.review_dev --diagnostics-only
```

Các lệnh kiểm tra không gọi embedding API. Cần thấy B: 701 chunks, 30 documents, 1536 dimensions; review_dev kiểm tra corpus hash.

Chỉ khi database mới chưa có index: tái tạo bằng DEV Day 6 tại commit được pin. Bước này gọi API và phát sinh phí; không cần chạy TEST Day 6.

```powershell
$Day7Root = (Get-Location).Path
New-Item -ItemType Directory -Force .\deps | Out-Null
git clone https://github.com/kientrungtd135/K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion.git .\deps\day6
git -C .\deps\day6 checkout 7aa3adc7a0bf794daa654156b06bf9743403b763
$Day6Env = Join-Path $Day7Root "deps\day6\starter\.env"
$EnvText = Get-Content -LiteralPath .\.env -Raw -Encoding UTF8
[System.IO.File]::WriteAllText($Day6Env, $EnvText, [System.Text.UTF8Encoding]::new($false))
Push-Location .\deps\day6\starter
try {
    docker compose -p day6_student_starter up -d --wait
    & "$Day7Root\.venv\Scripts\python.exe" -X utf8 -m src.run
} finally { Pop-Location }
& .\.venv\Scripts\python.exe -X utf8 -m src.day6_bridge
& .\.venv\Scripts\python.exe -X utf8 -m src.review_dev --diagnostics-only
```

DEV Day 6 tạo A/B/C; Day 7 chỉ đọc B. deps/ được ignore. Model/API thay đổi có thể làm vector hoặc ranking khác. Không xóa Docker volume chứa index để dọn repo.

## Kiểm tra và tổng hợp, không gọi API

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -X utf8 -m src.summarize_results
& .\.venv\Scripts\python.exe -X utf8 -m src.write_submission_docs
```

21 unit tests đã pass, gồm sáu guard tests v2. Unit tests không thay thế benchmark agent thật. Tổng hợp kiểm tra hash pipeline/review; không tự chấm semantic hoặc đổi AI-proposed thành human-confirmed.

## Chạy agent và tái lập thí nghiệm

Các lệnh sau có gọi API, phát sinh phí. Dùng output mới để giữ trace cũ:

```powershell
$RunTag = Get-Date -Format "yyyyMMdd_HHmmss"
& .\.venv\Scripts\python.exe -X utf8 -m src.agent_v2 --method auto --query-id d7-dev-q09 --output ".\results\reproduction\demo_$RunTag.json"
& .\.venv\Scripts\python.exe -X utf8 -m src.evaluate_agent --run-name "reproduce_v1_$RunTag"
& .\.venv\Scripts\python.exe -X utf8 -m src.evaluate_agent_v2 --run-name "reproduce_v2_$RunTag"
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
