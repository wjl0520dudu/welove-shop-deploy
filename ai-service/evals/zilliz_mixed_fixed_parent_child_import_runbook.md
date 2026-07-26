# Zilliz Mixed Fixed Parent-Child Import

This runbook imports the current candidate strategy into Zilliz Cloud:

- product knowledge: v2.1 semantic units (`marketing`, one `faq`, three-review `review` groups);
- general knowledge: fixed parent `1000/100`, child `500/50`;
- retrieval: product chunks return directly; general child hits are reranked and reconstructed from parent windows.

The import rebuilds records from the source JSON and static general documents. It does not copy records from a local Milvus collection.

## Collection Name

Use `knowledge_mixed_fixed_parent_child_v1` for this strategy. The historical name `knowledge_semantic_recursive_general_v1` describes a different strategy: product semantic chunks plus recursive single-layer general chunks.

The script permits a custom `--collection` name for an intentional migration, but it emits a warning when that historical recursive name is selected. A collection created by the recursive single-layer strategy has no `parent_id` or `child_index` fields, so it cannot be reused for this parent-child strategy without deleting and recreating it.

## Configure `ai-service/.env`

Set the Zilliz endpoint and token. Do not commit this file.

```env
MILVUS_URL=https://<cluster-endpoint>.zillizcloud.com
MILVUS_TOKEN=<zilliz-api-token>
MILVUS_COLLECTION=knowledge_mixed_fixed_parent_child_v1
MILVUS_DENSE_DIM=1024

RAG_PARENT_CHILD_ENABLED=true
RAG_PARENT_CHILD_CHUNKING=mixed_fixed_v1
RAG_PARENT_CHILD_GENERAL_ONLY=true
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

`CHUNK_SIZE` and `CHUNK_OVERLAP` remain the shared retrieval metadata. The mixed parent-child importer fixes its general-knowledge parent and child sizes internally at `1000/100` and `500/50`.

## Verify the Remote Connection

```powershell
cd D:\dev\project\py\welove-shop-agt\ai-service

python scripts/check_milvus_connection.py --remote
```

The command is read-only. It verifies that the endpoint is HTTPS and that a token is configured before it connects.

## Inspect the Chunk Plan

```powershell
python scripts/ingest_mixed_fixed_parent_child_v1.py `
  --collection knowledge_mixed_fixed_parent_child_v1 `
  --source all `
  --dry-run `
  --remote
```

This builds the records and prints counts without connecting to Milvus or calling the embedding API.

## Import or Reimport

For a new remote collection:

```powershell
python scripts/ingest_mixed_fixed_parent_child_v1.py `
  --collection knowledge_mixed_fixed_parent_child_v1 `
  --source all `
  --remote
```

For an existing collection created by this same strategy, use `--replace`. It deletes records for each incoming `doc_id` before inserting replacements. It does not drop the collection.

```powershell
python scripts/ingest_mixed_fixed_parent_child_v1.py `
  --collection knowledge_mixed_fixed_parent_child_v1 `
  --source all `
  --replace `
  --remote
```

If the target collection exists but uses a single-layer schema, the script stops before writes and reports the missing `parent_id` / `child_index` fields. Do not use `--replace` to solve that schema mismatch; create a new collection with the strategy name above, or explicitly drop the incorrect remote collection only after confirming it is disposable.
