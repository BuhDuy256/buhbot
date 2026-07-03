Bài viết này là một hướng dẫn tổng quan về **chunking** trong hệ thống RAG (Retrieval-Augmented Generation), từ khái niệm cơ bản đến các chiến lược hiện đại. 

Tóm tắt ngắn gọn:

* **Chunking là gì?**

  * Là quá trình chia tài liệu lớn thành nhiều đoạn nhỏ (chunk) để embedding và retrieval hiệu quả hơn.
  * Đây là một trong những yếu tố ảnh hưởng mạnh nhất đến chất lượng của RAG.

* **Vì sao chunking quan trọng?**

  * LLM có giới hạn context window.
  * Chunk tốt giúp:

    * embedding biểu diễn đúng ý nghĩa,
    * retrieval chính xác hơn,
    * giảm việc bỏ sót thông tin.
  * Chunk tệ sẽ cắt đứt ngữ cảnh hoặc chứa quá nhiều thông tin khiến retriever khó tìm đúng.

* **Chunking nằm ở đâu trong pipeline?**

  ```
  Document
      ↓
  Preprocessing
      ↓
  Chunking
      ↓
  Embedding
      ↓
  Vector DB
      ↓
  Retrieval
      ↓
  LLM
  ```

  Ngoài ra bài viết còn giới thiệu hai hướng mới:

  * Post-chunking: embed document trước, chunk khi query.
  * Late chunking: lưu embedding coarse, chia nhỏ khi retrieval.

---

## Các nguyên tắc khi thiết kế chunk

Một chunk tốt cần cân bằng 3 yếu tố:

1. Semantic coherence

   * Một chunk nên chứa một ý tưởng hoàn chỉnh.

2. Context preservation

   * Có đủ ngữ cảnh để hiểu khi đứng độc lập.

3. Computational efficiency

   * Không quá lớn cũng không quá nhỏ.

---

## Các chiến lược chunking

### 1. Fixed-size Chunking

Ví dụ:

* 500 tokens/chunk

Ưu điểm

* Rất đơn giản
* Nhanh
* Dễ implement

Nhược điểm

* Có thể cắt giữa câu hoặc giữa một ý.

=> Đây là cách phổ biến nhất hiện nay.

---

### 2. Sentence-based Chunking

Chia theo câu.

Ưu điểm

* Dễ đọc
* Không cắt giữa câu

Nhược điểm

* Độ dài chunk không đều.

---

### 3. Recursive Chunking

Chia theo cấu trúc:

```
Heading
    ↓
Paragraph
    ↓
Sentence
```

Nếu chunk còn quá lớn thì tiếp tục chia xuống cấp nhỏ hơn.

Đây chính là chiến lược của LangChain RecursiveCharacterTextSplitter.

---

### 4. Semantic Chunking

Không chia theo số token.

Thay vào đó:

* tính embedding từng câu
* đo semantic similarity
* khi chủ đề thay đổi thì tạo chunk mới

Ưu điểm

* Retrieval chính xác hơn

Nhược điểm

* Chi phí preprocessing cao.

---

### 5. Sliding Window Chunking

Ví dụ:

```
Chunk 1
[1........................500]

Chunk 2
            [251................750]
```

Overlap khoảng 20–50%.

Ưu điểm

* Không mất context ở biên.

Nhược điểm

* Tốn storage hơn.

---

### 6. Hierarchical Chunking

Lưu quan hệ cha-con:

```
Section
    ├── Paragraph
    │      ├── Sentence
```

Khi retrieve:

* có thể lấy cả section
* hoặc chỉ paragraph
* hoặc mở rộng từ sentence lên paragraph.

Phù hợp cho:

* luật
* tài liệu kỹ thuật
* báo cáo.

---

### 7. Contextual Chunking

Ngoài text còn lưu metadata:

* heading
* timestamp
* filename
* page
* source

Metadata giúp retrieval chính xác hơn.

---

### 8. Topic-based Chunking

Chunk theo chủ đề thay vì theo kích thước.

Ví dụ:

```
Topic A
Topic A
Topic A

↓

Chunk A
```

---

### 9. Modality-specific Chunking

Không phải dữ liệu nào cũng là text.

Ví dụ:

* bảng → chia theo hàng
* ảnh → chia theo vùng
* transcript → theo speaker

---

### 10. AI-driven Dynamic Chunking

Dùng chính LLM để quyết định:

"Đoạn nào nên chia?"

Thay vì rule cố định.

Ưu điểm

* Chunk rất tự nhiên.

Nhược điểm

* Chậm
* Tốn chi phí.

---

### 11. Agentic Chunking

Cấp cao hơn AI chunking.

Một AI Agent sẽ:

* đọc document
* hiểu document
* quyết định nên dùng chiến lược chunking nào.

Ví dụ:

Medical report:

```
History
↓

Semantic Chunk

Lab Result
↓

Table Chunk

Doctor Note
↓

Recursive Chunk
```

Đây là hướng hiện đại nhất nhưng cũng phức tạp nhất.

---

## Performance Evaluation

Không nên chỉ nhìn bằng cảm giác.

Cần đo bằng metric như:

* Context Precision
* Context Recall
* Context Relevancy
* Chunk Utilization
* Chunk Attribution

Sau đó A/B test:

* chunk size
* overlap
* top-K
* retrieval strategy

để tìm cấu hình tốt nhất.

---

## Kết luận

Không có một chiến lược chunking nào tốt nhất cho mọi bài toán.

Bài viết khuyến nghị:

* Bắt đầu với **Recursive Chunking + Overlap** cho đa số ứng dụng.
* Nếu cần độ chính xác cao hơn, chuyển sang **Semantic Chunking**.
* Với các hệ thống RAG phức tạp hoặc đa dạng tài liệu, cân nhắc **Hierarchical**, **Contextual**, hoặc **Agentic Chunking**.
* Luôn đánh giá bằng metric và A/B testing thay vì chọn chiến lược theo cảm tính. 
