# API Documentation Map

This file contains the map for various APIs used in the project.

## Zendesk API
- [Zendesk API Specification](zendesk/zendesk-api-specificcation.md)

## OpenAI API

### Assistants
- [Create Assistant](openai/assistant/create-assistant.md)
- [Retrieve Assistant](openai/assistant/retrieve-assistant.md)
- [Modify Assistant](openai/assistant/update-assistant.md) — binds a vector store via `tool_resources.file_search.vector_store_ids` (max 1 store/assistant)

### Vector Stores
- [OpenAI Vector Stores API Specification](openai/vector_stores/openai_vector_stores_api_specification.md)
- [Table of Contents](openai/vector_stores/table-of-contents.md)
- [Create a Vector Store](openai/vector_stores/create-a-vector-store.md)
- [Retrieve a Vector Store](openai/vector_stores/retrieve-a-vector-store.md)
- [List a Vector Store](openai/vector_stores/list-a-vector-store.md)
- [Update a Vector Store](openai/vector_stores/update-a-vector-store.md)
- [Delete a Vector Store](openai/vector_stores/delete-a-vector-store.md)
- [Search Vector Stores](openai/vector_stores/search.md)

### Files
- [OpenAI Files API Specification](openai/vector-store-files/openai_files_api_speficiation.md)
- [Create Vector Store File](openai/vector-store-files/create-vector-store-file.md)
- [Retrieve Vector Store File](openai/vector-store-files/retrieve-vector-store-file.md)
- [Retrieve Vector Store File Content](openai/vector-store-files/retrieve-vector-store-file-content.md)
- [List Vector Store Files](openai/vector-store-files/list-vectore-store-files.md)
- [Update Vector Store File Attributes](openai/vector-store-files/update-vector-store-file-attributes.md)
- [Delete Vector Store File](openai/vector-store-files/delete-vector-store-file.md)

### File Batches
- [Create Vector Store File Batch](openai/vector-store-file-batches/create-vector-store-file-batch.md)
- [Retrieve Vector Store File Batch](openai/vector-store-file-batches/retrieve-vector-store-file-batch.md)
- [List Vector Store Files in a Batch](openai/vector-store-file-batches/list-vector-store-files-in-a-batch.md)
- [Cancel a File Batch](openai/vector-store-file-batches/cancel-a-file-batch.md)
