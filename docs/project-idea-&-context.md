Data Engineering & AI – Interview Summary and Project Data Flow

Capgemini Ignite preparation → practical Azure / Databricks portfolio project


1. The core architecture template

The reusable structure prepared for technical consulting cases was:

Source → Ingestion → Storage → Transformation → Serving → Consumer

Cross-cutting:
Data Quality | Testing | Security | Logging & Monitoring | CI/CD | Governance

The important point is that the architecture pattern stays stable while the concrete technologies change. A good consultant should not force Databricks, Azure Data Factory, streaming or machine learning into every case. The first task is to understand the business need, data, latency, users, security requirements and existing technology stack.

Questions to clarify before choosing technology:

- What business decision or user problem are we solving?
- What are the data sources, formats and owners?
- How much data is produced, and how quickly does it arrive?
- What latency is actually required: daily, hourly, near-real-time or real-time?
- How reliable and complete is the source data?
- Who will consume the output: analysts, dashboards, ML models, applications or an LLM?
- What security, privacy and access-control requirements apply?
- What systems and cloud platform does the customer already use?
- How will we know that the solution works and continues to work?


2. Concepts covered during the Capgemini Ignite preparation

ETL vs. ELT:
ETL transforms before loading into the target platform. ELT loads raw data first and transforms it inside the analytical platform. Modern cloud architectures often use ELT because raw data can be retained and reprocessed, but the choice depends on architecture, compliance, cost and downstream needs.

Data pipeline:
An automated and repeatable flow that moves and processes data. ETL and ELT are patterns inside a broader pipeline. A production pipeline should be observable, testable, maintainable and recoverable.

Batch vs. streaming:
Batch processes data at intervals; streaming processes events continuously or near-real-time. The main decision factor is business latency, not simply data volume. Streaming adds operational complexity and should only be used when the business requires it.

Data lake, warehouse and database:
A data lake is flexible storage for raw and semi-structured data. A warehouse is optimized for structured analytics and reporting. An operational database supports applications and transactions. A lakehouse combines data-lake flexibility with warehouse-style structure and reliability.

Bronze / Silver / Gold:
Bronze stores raw or minimally changed data.
Silver contains cleaned, standardized and trusted data.
Gold contains business- or use-case-ready datasets for reporting, analytics or ML.

Databricks / Spark / Delta Lake:
Databricks is the working platform.
Spark is the distributed processing engine.
SQL or PySpark are interfaces used to transform data.
Delta Lake adds reliable table semantics such as ACID transactions, schema enforcement and versioning.

Data quality:
Core dimensions include completeness, accuracy, consistency, uniqueness, validity and freshness. A technically successful pipeline can still produce bad business data.

Testing:
Unit tests validate isolated logic.
Integration tests validate components together.
End-to-end tests validate the complete flow.
Regression tests detect unintended changes.
Schema and data-quality tests should be part of production pipelines.

APIs and files:
API ingestion requires handling authentication, secrets, pagination, rate limits, retries, timeouts and schema changes.

File ingestion requires checks for:
- existence
- schema
- data types
- nulls
- duplicates
- plausible row counts

RAG:
Retrieval-Augmented Generation retrieves relevant information and supplies it to an LLM as context. It does not train the LLM on the company documents.

A secure enterprise RAG system must enforce document-level access control during retrieval.


3. Recommended portfolio project

Project idea:
Energy Market Analytics & Forecasting Platform

Build a platform that:

- ingests electricity-price data
- ingests weather data
- optionally ingests energy-system or hydrological data
- stores raw history
- cleans and combines the datasets
- creates analytics-ready Gold tables
- trains a simple forecasting model
- serves outputs to a dashboard or API

Why this is a strong portfolio project:

- It demonstrates end-to-end data engineering rather than isolated data science.
- It naturally supports Data Lake concepts and Bronze/Silver/Gold.
- It gives a realistic reason to use SQL, Python/PySpark and Delta tables.
- Machine learning becomes a downstream consumer of well-engineered data instead of the entire project.
- The energy domain connects naturally to experience from Å Energi and hydropower optimization.
- The architecture is easy to explain in a technical interview.


4. Detailed data flow

External Sources
        ↓
Ingestion / orchestration
        ↓
Raw storage – Bronze
        ↓
Databricks – validation, cleaning, joins
        ↓
Delta Lake – Silver
        ↓
Databricks – business logic / feature engineering
        ↓
Delta Lake – Gold
        ↓
ML model + SQL endpoint / API
        ↓
Dashboard / application / analyst


4.1 Source

Possible sources:

- Electricity-price API
  - timestamp
  - price area
  - EUR/MWh or NOK/MWh

- Weather API
  - temperature
  - precipitation
  - wind
  - forecasts

- Static reference data
  - price areas
  - station metadata
  - geographic mappings

- Historical CSV / Parquet files
  - useful for backfills

At this stage, do not clean the data aggressively.

Instead establish:
- source of truth
- update frequency
- identifiers
- timestamps
- expected schema


4.2 Ingestion

The ingestion/orchestration layer is responsible for moving data into the platform.

Responsibilities:

- Run API ingestion on a schedule.
- Support both incremental loads and historical backfills.
- Keep secrets outside source code.
- Handle retries.
- Handle timeouts.
- Log ingestion timestamp.
- Log row count.
- Log pipeline run ID.
- Log success/failure.
- Prefer incremental loading when appropriate.

Important distinctions:

Pagination:
Controls how data is retrieved in portions.

Incremental loading:
Controls which records are retrieved.

Rate limiting:
Controls how frequently the source allows requests.


4.3 Storage – Bronze

Raw data should be stored before business transformations.

Example:

bronze/
    prices/
        year=2026/
            month=10/
                day=20/
    weather/
    reference/

Principles:

- Preserve the original payload where practical.
- Add ingestion metadata.
- Store source information.
- Keep the raw history.
- Avoid overwriting raw data unless there is a deliberate retention policy.
- Prefer append-oriented Bronze storage.

Why this matters:

If transformation logic changes later, Silver and Gold can be rebuilt from the original data instead of downloading everything again.


4.4 Transformation – Bronze to Silver

This is where raw data becomes standardized and trusted.

Typical transformations:

- Parse timestamps.
- Normalize timezone.
- Standardize units.
- Standardize column names.
- Enforce schemas.
- Enforce data types.
- Remove exact duplicates.
- Check required fields.
- Quarantine invalid records.
- Validate ranges.
- Create stable business keys.
- Join sources after validating keys.
- Write validated data as Delta tables.

Example business key:

price_area + timestamp

Important principle:

An outlier is not automatically bad data.

For example:
- an extreme electricity price may be real
- an extreme temperature may be real
- an unusual sensor value may represent an actual event

Invalid values can be rejected or quarantined.
Unusual but plausible values should generally be retained and possibly flagged.


4.5 Silver layer

Silver should contain reusable and trusted domain tables.

Examples:

silver.power_prices
silver.weather_hourly
silver.calendar
silver.price_area_reference

Silver data should be suitable for reuse by:

- analytics
- dashboards
- ML pipelines
- downstream applications


4.6 Gold transformation

Gold is optimized for a specific consumer or business use case.

Example forecasting Gold table:

One row per:

price_area + timestamp

Possible features:

- current electricity price
- lagged prices
- rolling average
- price volatility
- temperature
- precipitation
- wind
- hour of day
- weekday
- month
- holiday indicator
- reservoir/hydrological variables
- prediction target

Important distinction:

Silver:
trusted and reusable

Gold:
use-case specific


4.7 Machine-learning pipeline

The ML model should consume Gold data.

Pipeline:

Gold data
    ↓
Train / validation / test split
    ↓
Baseline model
    ↓
Stronger model
    ↓
Evaluation
    ↓
Prediction table

Important:

Split time-series data chronologically.

Do not randomly shuffle if this creates time leakage.

Start with a simple baseline, for example:

- previous-hour price
- previous-day same-hour price
- linear regression

Then compare a stronger model.

Possible metrics:

- MAE
- RMSE

Track:

- model version
- training period
- feature set
- metrics
- parameters

Write predictions back to a Gold prediction table.

Monitor model performance after deployment.

Do not use ML just because you can.

First demonstrate that:
1. it beats a simple baseline
2. it creates actual business value


4.8 Serving

Serving exposes trusted data to users or applications.

Possible outputs:

- Gold analytics tables
- SQL endpoint
- REST API
- DuckDB queries
- Power BI
- Streamlit

Prediction table might contain:

- forecast timestamp
- target timestamp
- price area
- predicted price
- model version
- prediction horizon


4.9 Consumer

Consumers might include:

- analyst
- trader
- planner
- manager
- application
- ML workflow

A dashboard could show:

- historical prices
- weather
- latest forecast
- next-day forecast
- model error
- pipeline status
- data freshness


5. Cross-cutting production concerns


Data quality

Check:

Completeness:
Are expected records missing?

Uniqueness:
Are business keys duplicated?

Validity:
Are types, ranges and categories valid?

Consistency:
Do datasets use the same identifiers and units?

Freshness:
Did the latest data arrive on time?

Accuracy:
Where possible, compare important numbers against the source.


Testing

Use:

- Unit tests
- Schema tests
- Integration tests
- End-to-end tests
- Regression tests

Examples:

Unit:
Test one transformation function.

Integration:
Test Bronze → Silver processing.

End-to-end:
Provide known input and verify expected Gold output.

Regression:
Ensure an important aggregate or calculation has not unexpectedly changed.


Security

Principles:

- Never commit secrets.
- Use environment variables or a secret manager.
- Follow least privilege.
- Separate development and production where relevant.
- Restrict sensitive datasets.
- Apply access control at the data level, not only in the dashboard.


Logging, monitoring and alerting

Logging:
What happened?

Monitoring:
Is the system behaving correctly?

Alerting:
Does someone need to act?

Monitor:

- pipeline status
- execution time
- rows ingested
- rows rejected
- rows written
- data freshness
- missing partitions
- schema changes
- ML prediction error
- model drift

Alerts should be actionable.


CI/CD

Code should live in Git.

Example workflow:

feature branch
    ↓
pull request
    ↓
automated tests
    ↓
merge
    ↓
deployment

CI/CD can automate:

- linting
- tests
- packaging
- deployment
- configuration validation

Important:

CI/CD does not replace data-quality testing.


Governance

Document:

- dataset owner
- business definition
- schema
- lineage
- retention policy
- authoritative source
- access requirements

A data catalog can help make this discoverable.


6. How to reason when something is wrong

If a dashboard number is wrong, trace backwards:

Consumer / Gold
        ↓
Silver
        ↓
Bronze
        ↓
Source

Process:

1. Check whether the discrepancy exists in Gold.
2. Compare Gold and Silver aggregates.
3. Inspect joins.
4. Inspect filters.
5. Inspect business rules.
6. Check reference/master data.
7. Compare Silver with Bronze.
8. Compare Bronze with Source.
9. Review pipeline logs.

Example:

Sales data:

sales
LEFT / INNER JOIN
product master

If a new product is missing from the master table:

INNER JOIN:
sales rows disappear

LEFT JOIN:
sales rows remain
missing product metadata becomes NULL

Then the missing master-data issue can be flagged and investigated.


7. Applying the same architecture to RAG

The same model applies:

Source
    ↓
Ingestion
    ↓
Storage
    ↓
Transformation
    ↓
Serving
    ↓
Consumer


Source

Examples:

- HR policies
- technical documentation
- project reports
- procedures
- internal knowledge documents


Ingestion

Possible methods:

- APIs
- connectors
- scripts
- scheduled ingestion


Storage

Store original documents.

Reasons:

- traceability
- reprocessing
- versioning


Transformation

For RAG, transformation differs from tabular data.

Typical steps:

- text extraction
- document deduplication
- remove outdated versions
- metadata standardization
- chunking
- embeddings
- access metadata


Serving

Typical serving layer:

- vector database
- vector index
- search service
- optionally a Knowledge Graph


Query flow:

User question
      ↓
Embedding / search
      ↓
Retrieve relevant chunks
      ↓
Supply chunks to LLM
      ↓
Generate grounded answer


Consumer

Internal assistant
      ↓
Employee


Critical security rule:

Document access must follow the data through the entire pipeline.

The retrieval layer must only return document chunks that the current user is authorized to access.


RAG evaluation

Separate:

Retrieval quality:
Did we retrieve the right information?

Generation quality:
Did the LLM use that information correctly?

A bad answer may be caused by poor retrieval even if the LLM itself works correctly.


8. How to explain the project in an interview

Example:

“I built an end-to-end data platform rather than only a machine-learning notebook.

Data is ingested from external energy and weather sources and stored raw so the pipeline is reproducible.

The data is then transformed through Bronze, Silver and Gold layers with explicit data-quality checks.

Silver contains trusted reusable domain data, while Gold contains analytics-ready and model-ready datasets.

A forecasting model consumes Gold data, and its predictions are written back to a serving table used by a dashboard.

Around the pipeline I added testing, logging, monitoring, security and CI/CD.

The main thing I wanted to demonstrate was that useful machine learning depends on reliable data engineering.”


9. What this project should prove to a consulting employer

The project should demonstrate that:

- You can structure an ambiguous data problem.
- You understand why each architecture layer exists.
- You can distinguish ingestion, storage, transformation, serving and consumption.
- You understand production concerns beyond notebook code.
- You understand trade-offs.
- You avoid unnecessary complexity.
- You understand that ML and GenAI depend on reliable data platforms.
- You can communicate architecture clearly.
- You can explain technical choices to non-technical people.


10. Suggested implementation order

Because you want free tools long-term, I would now slightly modify the original implementation plan:

1. Build the project locally using Python.
2. Select one electricity-price API.
3. Select one weather API.
4. Store raw data locally in a Bronze folder structure.
5. Add Apache Airflow for orchestration.
6. Use Databricks Free Edition for PySpark + Delta Lake transformations.
7. Implement Bronze → Silver → Gold.
8. Add schema and data-quality tests.
9. Add a baseline forecasting model using scikit-learn.
10. Track ML experiments with MLflow.
11. Write predictions to Gold.
12. Use DuckDB for analytical querying where useful.
13. Build a Streamlit dashboard or Power BI Desktop dashboard.
14. Add logging and monitoring.
15. Add pytest tests.
16. Add GitHub Actions CI.
17. Document data lineage and architecture in README.


11. Final mental model

Business need
        ↓

Source
        ↓
Ingestion
        ↓
Storage
        ↓
Transformation
        ↓
Serving
        ↓
Consumer

Across everything:

Data Quality
Testing
Security
Logging & Monitoring
CI/CD
Governance

        ↓

Reliable analytics / ML / AI / decision support