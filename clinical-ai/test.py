from app.rag.retriever import retrieve

results = retrieve("fever cough high WBC")
for r in results:
    print(r["name"])