# ingest theory excerpts
curl -X POST http://localhost:8000/rag/ingest/ \
  -F namespace=theory \
  -F doc_id=theory_demo \
  -F file=@demo_data/theory_excerpts.txt

# ingest personal safety plan
curl -X POST http://localhost:8000/rag/ingest/ \
  -F namespace=personal_plan \
  -F doc_id=plan_demo \
  -F file=@demo_data/personal_plan.txt

# ingest past session notes
curl -X POST http://localhost:8000/rag/ingest/ \
  -F namespace=session_data \
  -F doc_id=session_demo \
  -F file=@demo_data/session_notes.txt

# ingest future-me persona
curl -X POST http://localhost:8000/rag/ingest/ \
  -F namespace=future_me \
  -F doc_id=future_demo \
  -F file=@demo_data/future_me_profile.txt
