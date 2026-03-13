## Data model

* **Why `mailbox.displayName`**
  It allows search results to be rendered directly from the mailbox collection without loading user or team entities, keeping the hottest path fast and branch-free. It is a derived, UI-facing cache that decouples search and rendering from relationship traversal.

* **Why we have a `MAILBOX` entity**
  Mailbox is the single interaction and ownership boundary for mail and search, collapsing users and teams into a uniform, queryable surface. This removes polymorphic mail ownership and makes search, navigation, and mail queries predictable and indexable.

* **Why `teamId` is embedded on the user side**
  The relationship is many-users-to-one-team and expansion is always user -> team, so storing the foreign key on the user keeps reads simple and bounded. This avoids joins, matches MongoDB's ownership model, and reflects the actual access pattern.

* **Why MAIL entries are individual documents (no `count` field)**
  Each mail document represents one physical piece of mail. The previous cumulative `count` model was replaced because the OCR-driven intake flow captures metadata (receiver name, sender info) per individual item. Counts are derived by counting documents rather than summing a field. This makes the data model truthful to the physical process: admin scans one piece of mail, confirms extracted data, and saves one document.

* **Why `receiverName` replaced `receiverAddress`**
  The primary OCR extraction target is the receiver's name or company, not the full mailing address. The field was renamed to reflect the actual data being captured and the user-facing label in the admin form. Full address text can still be stored in this field when available.

* **Why self-hosted PaddleOCR as the default OCR provider**
  PaddleOCR is a PaddlePaddle-based deep-learning OCR engine with the highest accuracy in benchmarks for real-world images (15% CER on receipts vs 20% for EasyOCR). Tesseract (traditional OCR) produced garbled text on package labels. EasyOCR was tried but produced incomplete results on envelopes and was slow on CPU. PaddleOCR uses an 8.6M ultra-lightweight model with angle classification for rotated text. All four providers remain selectable via the `OCR_PROVIDER` environment variable (`paddleocr`, `easyocr`, `tesseract`, or `ocrspace`).
