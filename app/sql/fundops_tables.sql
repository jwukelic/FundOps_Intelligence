CREATE SCHEMA IF NOT EXISTS `fundops`;

CREATE TABLE IF NOT EXISTS `fundops.signals` (
  observed_date DATE,
  observed_at TIMESTAMP,
  salesforce_account_id STRING,
  salesforce_opportunity_id STRING,
  program STRING,
  signal_type STRING,
  external_id STRING,
  strength INT64,
  confidence INT64,
  summary STRING,
  source_name STRING,
  source_url STRING,
  raw_hash STRING
)
PARTITION BY observed_date
CLUSTER BY salesforce_account_id, salesforce_opportunity_id, program, signal_type;

CREATE TABLE IF NOT EXISTS `fundops.scores` (
  score_date DATE,
  scored_at TIMESTAMP,
  salesforce_account_id STRING,
  program STRING,
  total_score INT64,
  priority STRING,
  mission_and_program_fit FLOAT64,
  funding_capacity FLOAT64,
  timing_and_current_intent FLOAT64,
  relationship_access FLOAT64,
  internal_readiness FLOAT64,
  engagement_momentum FLOAT64,
  data_confidence FLOAT64,
  explanation STRING
)
PARTITION BY score_date
CLUSTER BY salesforce_account_id, program;

CREATE TABLE IF NOT EXISTS `fundops.sync_state` (
  connector STRING,
  state_key STRING,
  state_value STRING,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `fundops.ai_cache` (
  cache_date DATE,
  cache_key STRING,
  input_hash STRING,
  model STRING,
  output_json STRING,
  created_at TIMESTAMP
)
PARTITION BY cache_date
CLUSTER BY cache_key;

CREATE TABLE IF NOT EXISTS `fundops.content_index` (
  indexed_date DATE,
  file_id STRING,
  file_name STRING,
  program STRING,
  source_url STRING,
  text_hash STRING,
  approval_status STRING,
  updated_at TIMESTAMP
)
PARTITION BY indexed_date
CLUSTER BY program;

CREATE TABLE IF NOT EXISTS `fundops.audit_log` (
  audit_date DATE,
  event_at TIMESTAMP,
  entity_type STRING,
  entity_id STRING,
  field_name STRING,
  old_value STRING,
  new_value STRING
)
PARTITION BY audit_date
CLUSTER BY entity_type, entity_id;

CREATE TABLE IF NOT EXISTS `fundops.connector_runs` (
  run_date DATE,
  run_at TIMESTAMP,
  connector STRING,
  status STRING,
  processed_count INT64,
  error_count INT64,
  error_summary STRING
)
PARTITION BY run_date
CLUSTER BY connector;

CREATE TABLE IF NOT EXISTS `fundops.opportunity_intake` (
  intake_date DATE,
  row_id STRING,
  source_url STRING,
  organization STRING,
  program STRING,
  opportunity_type STRING,
  process_status STRING,
  salesforce_opportunity_id STRING,
  last_processed TIMESTAMP,
  error STRING
)
PARTITION BY intake_date
CLUSTER BY program, process_status;
