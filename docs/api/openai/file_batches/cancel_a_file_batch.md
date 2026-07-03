# Cancel a file batch

## Cancel a vector store file batch

**POST** `/v1/vector_stores/{vector_store_id}/file_batches/{batch_id}/cancel`

Cancel a vector store file batch.

### Path Parameters

- **vector_store_id** (string, required): The ID of the vector store.
- **batch_id** (string, required): The ID of the file batch to cancel.

### Response
Returns the modified vector store file batch object.
