CREATE SCHEMA IF NOT EXISTS `fundops`;

CREATE TABLE IF NOT EXISTS `fundops.signals` (
  signal_id STRING NOT NULL,
  connector STRING NOT NULL,
  entity_type STRING NOT NULL,
  entity_key STRING NOT NULL,
  signal_type STRING NOT NULL,
  score FLOAT64 NOT NULL,
  external_id STRING,
  source_id STRING,
  source_url STRING,
  summary STRING,
  raw_text STRING,
  metadata JSON,
  observed_at TIMESTAMP,
  raw_hash STRING
)
PARTITION BY DATE(observed_at)
CLUSTER BY connector, entity_type, entity_key;

CREATE TABLE IF NOT EXISTS `fundops.scores` (
  score_id STRING NOT NULL,
  entity_key STRING NOT NULL,
  entity_type STRING NOT NULL,
  total_score FLOAT64 NOT NULL,
  priority STRING NOT NULL,
  reasons ARRAY<STRING>,
  supporting_sources ARRAY<STRING>,
  scored_at TIMESTAMP
)
CLUSTER BY entity_type, entity_key;

CREATE TABLE IF NOT EXISTS `fundops.sync_state` (
  connector_name STRING NOT NULL,
  watermark STRING,
  updated_at TIMESTAMP
)
CLUSTER BY connector_name;

CREATE TABLE IF NOT EXISTS `fundops.ai_cache` (
  input_hash STRING NOT NULL,
  response_json STRING NOT NULL,
  updated_at TIMESTAMP
)
CLUSTER BY input_hash;

CREATE TABLE IF NOT EXISTS `fundops.content_index` (
  content_id STRING NOT NULL,
  connector STRING NOT NULL,
  entity_key STRING NOT NULL,
  title STRING NOT NULL,
  text STRING NOT NULL,
  approved BOOL NOT NULL,
  source_url STRING,
  metadata JSON,
  updated_at TIMESTAMP
)
PARTITION BY DATE(updated_at)
CLUSTER BY connector, entity_key;

CREATE TABLE IF NOT EXISTS `fundops.audit_log` (
  target_type STRING NOT NULL,
  target_id STRING NOT NULL,
  action STRING NOT NULL,
  before JSON,
  after JSON,
  changed_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(changed_at)
CLUSTER BY target_type, target_id;

CREATE TABLE IF NOT EXISTS `fundops.connector_runs` (
  connector_name STRING NOT NULL,
  status STRING NOT NULL,
  error_message STRING,
  ran_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(ran_at)
CLUSTER BY connector_name, status;

CREATE TABLE IF NOT EXISTS `fundops.opportunity_intake` (
  external_id STRING NOT NULL,
  account_key STRING NOT NULL,
  name STRING NOT NULL,
  amount FLOAT64,
  stage_name STRING NOT NULL,
  close_date DATE,
  source_url STRING,
  metadata JSON,
  updated_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(updated_at)
CLUSTER BY account_key, stage_name;

