# RAG Evaluation Results

## Framework sử dụng

Sử dụng lightweight deterministic evaluator theo phong cách RAGAS/DeepEval: metric được tính bằng token overlap giữa expected answer/context và retrieved context. Cách này chạy local ổn định, không tốn thêm LLM judge quota, và vẫn bao phủ 4 metric bắt buộc.

## Overall Scores

| Metric | Config A: hybrid + rerank | Config B: hybrid no rerank | Δ |
|---|---:|---:|---:|
| Faithfulness | 0.995 | 0.997 | -0.002 |
| Answer Relevance | 0.722 | 0.719 | 0.003 |
| Context Recall | 0.983 | 0.995 | -0.011 |
| Context Precision | 0.855 | 0.926 | -0.071 |
| Average | 0.889 | 0.909 | -0.021 |

## A/B Comparison Analysis

**Config A:** Hybrid retrieval gồm semantic search + BM25, merge bằng RRF và rerank bằng Jina.

**Config B:** Hybrid retrieval gồm semantic search + BM25, merge bằng RRF nhưng không rerank.

**Kết luận:** Config có điểm Average cao hơn là cấu hình được khuyến nghị cho demo. Nếu Config A tốt hơn, reranking giúp đưa context liên quan lên đầu; nếu Config B tốt hơn hoặc tương đương, có thể ưu tiên B khi cần giảm chi phí API.

## Worst Performers (Bottom 3 - Config A)

| # | Question | Faithfulness | Relevance | Recall | Precision | Retrieved Sources |
|---|---|---:|---:|---:|---:|---|
| 13 | Số tiền giao dịch mua bán ma túy mà cơ quan điều tra làm rõ trong chuyên án là bao nhiêu? | 1.000 | 0.500 | 1.000 | 0.462 | article_01.md, article_02.md, article_02.md |
| 3 | Ca sĩ Chi Dân và người mẫu An Tây bị bắt vì hành vi gì liên quan đến ma túy? | 1.000 | 0.385 | 1.000 | 0.688 | article_01.md, article_02.md, article_03.md |
| 4 | Nghị định 105/2021/NĐ-CP quy định gì về việc nhập khẩu, xuất khẩu chất ma túy và tiền chất? | 1.000 | 0.545 | 1.000 | 0.667 | luat-phong-chong-ma-tuy-2021.md, 105.2021.ND.CP.md, 105.2021.ND.CP.md |

## Recommendations

### Cải tiến 1
**Action:** Bổ sung thêm văn bản pháp luật còn thiếu nếu golden dataset mở rộng sang các nghị định/danh mục chưa có trong corpus.  
**Expected impact:** Tăng context recall cho các câu hỏi pháp luật chuyên sâu.

### Cải tiến 2
**Action:** Chuẩn hóa và làm giàu metadata source, ví dụ tên văn bản, số điều, ngày bài báo.  
**Expected impact:** Citation đẹp hơn và context precision dễ phân tích hơn.

### Cải tiến 3
**Action:** Điều chỉnh top_k và ngưỡng fallback PageIndex cho các câu hỏi khó.  
**Expected impact:** Giảm nguy cơ thiếu evidence khi câu hỏi cần nhiều đoạn chứng cứ.
