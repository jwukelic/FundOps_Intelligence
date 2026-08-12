-- Read cached AI response by hash
SELECT response_json FROM `fundops.ai_cache` WHERE input_hash = @input_hash LIMIT 1;

-- Read connector watermark
SELECT watermark FROM `fundops.sync_state` WHERE connector_name = @connector_name LIMIT 1;

-- Retrieve approved content by entity
SELECT content_id, title, text, source_url
FROM `fundops.content_index`
WHERE entity_key = @entity_key AND approved = TRUE
ORDER BY updated_at DESC
LIMIT 5;
