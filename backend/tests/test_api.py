"""End-to-end API tests: auth, problems, AI endpoints, teams, feedback, admin.

Runs against a fresh seeded SQLite database (see conftest)."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login(client):
    r = client.post(
        "/api/auth/register",
        json={
            "name": "Test Citizen X",
            "email": "testx@example.com",
            "password": "secret123",
            "role": "citizen",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["role"] == "citizen"
    assert body["access_token"]

    r = client.post(
        "/api/auth/login",
        json={"email": "testx@example.com", "password": "wrongpass"},
    )
    assert r.status_code == 401

    r = client.post(
        "/api/auth/login",
        json={"email": "testx@example.com", "password": "secret123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "testx@example.com"


def test_admin_cannot_be_registered_via_api(client):
    r = client.post(
        "/api/auth/register",
        json={
            "name": "Evil Admin",
            "email": "evil@example.com",
            "password": "secret123",
            "role": "admin",
        },
    )
    assert r.status_code == 422  # role pattern rejects admin


def test_citizen_cannot_access_admin_stats(client, citizen_token):
    r = client.get("/api/admin/statistics", headers={"Authorization": f"Bearer {citizen_token}"})
    assert r.status_code == 403


def test_admin_statistics(client, admin_token):
    r = client.get("/api/admin/statistics", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["total_problems"] >= 20
    assert s["duplicate_reports"] >= 3  # seed contains intentional duplicates
    assert s["registered_teams"] >= 6
    assert s["clusters"] >= 2
    assert s["total_recommendations"] > 0
    assert "by_category" in s and "by_status" in s


def test_model_performance(client, admin_token):
    """Model-performance must be HONEST: with no human-labelled evaluation
    data present (the synthetic labels are gone) it reports the absence
    explicitly instead of returning fabricated numbers."""
    r = client.get("/api/admin/model-performance", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    perf = r.json()

    # No labelled pairs / relevance rows -> explicit error, NOT fake metrics.
    assert perf["duplicate_detection"].get("error") == "no labelled evaluation pairs"
    assert "precision" not in perf["duplicate_detection"]  # nothing invented
    assert perf["team_matching"].get("error") == "no labelled relevance data"

    # Real labelling status (Data & Labels) is always reported.
    lab = perf["labeling"]
    assert "minima_for_training" in lab and "ready_to_train" in lab
    assert "real_corpus_rows" in lab

    # Clustering on the demo problems is a live-inference metric and still works.
    assert 0 <= perf["clustering"]["purity"] <= 1


def test_submit_problem_and_duplicate_detection(client, citizen_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    r = client.post(
        "/api/problems",
        headers=h,
        json={
            "title": "Street light completely dark on MG Road",
            "description": "The street light near the bus stop on MG road is not working at all. It is very dark and dangerous to walk at night.",
            "location": "MG Road",
            "category": "street_light",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    pid = body["problem"]["id"]
    analysis = body["analysis"]
    # should find the seeded street-light problems as similar
    assert len(analysis["similar_problems"]) > 0
    assert all("score" in s for s in analysis["similar_problems"])
    assert analysis["recommended_teams"]
    assert analysis["recommended_teams"][0]["ranking"] == 1

    # now submit a near-duplicate of the one we just created
    r2 = client.post(
        "/api/problems",
        headers=h,
        json={
            "title": "Street lamp off on MG Road",
            "description": "Street light near the bus stop on MG road has stopped working. Total darkness at night, very unsafe.",
            "location": "MG Road",
            "category": "street_light",
        },
    )
    assert r2.status_code == 201, r2.text
    p2 = r2.json()["problem"]
    assert p2["is_duplicate"] is True
    assert p2["duplicate_of"] is not None
    assert p2["duplicate_of"]["id"] == pid


def test_problems_crud_and_access_control(client, citizen_token, admin_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    r = client.post(
        "/api/problems",
        headers=h,
        json={
            "title": "Broken bench in central park",
            "description": "A wooden bench in the central park is broken with sharp splinters. Children play nearby.",
            "location": "Central Park",
            "category": "public_space",
        },
    )
    pid = r.json()["problem"]["id"]

    # owner can read
    assert client.get(f"/api/problems/{pid}", headers=h).status_code == 200

    # update
    r = client.put(
        f"/api/problems/{pid}",
        headers=h,
        json={"description": "A wooden bench in the central park is broken, with sharp splinters. Children play nearby and could get hurt."},
    )
    assert r.status_code == 200

    # other citizen cannot read
    r = client.post(
        "/api/auth/register",
        json={"name": "Other Citizen", "email": "other@example.com", "password": "secret123"},
    )
    other_token = r.json()["access_token"]
    assert client.get(
        f"/api/problems/{pid}", headers={"Authorization": f"Bearer {other_token}"}
    ).status_code == 403

    # admin can read and delete
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    assert client.get(f"/api/problems/{pid}", headers=h_admin).status_code == 200
    assert client.delete(f"/api/problems/{pid}", headers=h_admin).status_code == 204
    assert client.get(f"/api/problems/{pid}", headers=h).status_code == 404


def test_similar_problems_endpoint(client, citizen_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    r = client.get("/api/problems", headers=h)
    assert r.status_code == 200
    pid = r.json()[0]["id"]
    r = client.get(f"/api/ai/similar-problems/{pid}?k=3", headers=h)
    assert r.status_code == 200
    assert len(r.json()["similar"]) <= 3


def test_check_duplicate_endpoint(client, citizen_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    problems = client.get("/api/problems", headers=h).json()
    # find a seeded duplicate problem if present, else any
    dup = next((p for p in problems if p["is_duplicate"]), problems[0])
    r = client.post("/api/ai/check-duplicate", headers=h, json={"problem_id": dup["id"]})
    assert r.status_code == 200
    body = r.json()
    assert "threshold" in body
    if dup["is_duplicate"]:
        assert body["is_duplicate"] is True
        assert body["duplicate_of"]["id"] == dup["duplicate_of"]["id"]


def test_clusters_endpoint(client, citizen_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    r = client.get("/api/ai/clusters", headers=h)
    assert r.status_code == 200
    clusters = r.json()
    assert len(clusters) >= 2
    total_members = sum(c["size"] for c in clusters)
    assert total_members > 0
    assert all("name" in c and "members" in c for c in clusters)


def test_recommend_teams_endpoint(client, citizen_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    problems = client.get("/api/problems", headers=h).json()
    pid = problems[0]["id"]
    r = client.get(f"/api/ai/recommend-teams/{pid}?k=3", headers=h)
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert 0 < len(recs) <= 3
    scores = [x["score"] for x in recs]
    assert scores == sorted(scores, reverse=True)
    assert all(x["explanation"] for x in recs)  # explainable matching


def test_team_registration_and_flow(client):
    # register a fresh team account
    r = client.post(
        "/api/auth/register",
        json={
            "name": "Fresh Team Lead",
            "email": "freshteam@example.com",
            "password": "secret123",
            "role": "team",
        },
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/teams",
        headers=h,
        json={
            "team_name": "Fresh Team",
            "description": "We work on street lighting and smart city IoT.",
            "skills": ["python", "iot", "street lights"],
            "interests": ["public lighting", "smart city"],
            "experience": "Fixed solar street lights in a village project.",
            "members": [{"name": "Alpha", "role": "lead"}, {"name": "Beta", "role": "dev"}],
        },
    )
    assert r.status_code == 201, r.text
    team_id = r.json()["id"]
    assert r.json()["members"][0]["role"] == "lead"

    # cannot create a second team
    r2 = client.post(
        "/api/teams",
        headers=h,
        json={"team_name": "Second Team", "skills": ["python"]},
    )
    assert r2.status_code == 409

    # list + detail
    assert client.get("/api/teams", headers=h).status_code == 200
    detail = client.get(f"/api/teams/{team_id}", headers=h).json()
    assert detail["team_name"] == "Fresh Team"
    assert "street lights" in detail["skills"]

    # recommendations for my team
    r = client.get("/api/teams/my-recommendations", headers=h)
    assert r.status_code == 200
    recs = r.json()
    assert isinstance(recs, list)
    assert all("match_id" in x and "explanation" in x for x in recs)

    # accept the top recommendation for a street-light problem
    street = [x for x in recs if "light" in x["title"].lower()]
    if street:
        target = street[0]
        r = client.post(
            f"/api/teams/matches/{target['match_id']}/decision",
            headers=h,
            json={"status": "accept"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "accepted"
        assert r.json()["problem_status"] == "assigned"


def test_feedback_flow(client, citizen_token, admin_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    problems = client.get("/api/problems", headers=h).json()
    r = client.post(
        "/api/feedback",
        headers=h,
        json={
            "feedback_type": "wrong_duplicate",
            "problem_id": problems[0]["id"],
            "comment": "This was flagged as duplicate but it is a different incident.",
        },
    )
    assert r.status_code == 201, r.text

    mine = client.get("/api/feedback/mine", headers=h).json()
    assert len(mine) >= 1
    assert mine[0]["feedback_type"] == "wrong_duplicate"

    admin_fb = client.get("/api/feedback", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert any(f["id"] == mine[0]["id"] for f in admin_fb)


def test_cookie_auth_fallback(client):
    """Auth via the civic_token cookie (proxies that strip Authorization)."""
    r = client.post(
        "/api/auth/login",
        json={"email": "citizen1@civic.demo", "password": "demo123"},
    )
    token = r.json()["access_token"]
    client.cookies.set("civic_token", token)
    try:
        # NO Authorization header here - cookie must carry the session.
        r = client.get("/api/problems")
        assert r.status_code == 200, r.text
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "citizen1@civic.demo"
    finally:
        client.cookies.clear()


def test_logout_revokes_token(client):
    r = client.post(
        "/api/auth/register",
        json={"name": "Logout Tester", "email": "logout@example.com", "password": "secret123"},
    )
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    r = client.post("/api/auth/logout", headers=h)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_analysis_endpoint_shows_nlp_pipeline(client, citizen_token):
    h = {"Authorization": f"Bearer {citizen_token}"}
    problems = client.get("/api/problems", headers=h).json()
    pid = problems[0]["id"]
    r = client.get(f"/api/ai/analysis/{pid}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["problem_id"] == pid
    assert body["embedder"] in ("tfidf", "sentence")
    assert "threshold" in body and 0 < body["threshold"] < 1
    nlp = body["nlp"]
    assert nlp["token_count"] > 0
    assert len(nlp["tokens"]) == nlp["token_count"]
    assert nlp["top_keywords"]
    assert all(len(t) >= 3 for t, _ in nlp["top_keywords"])  # no stopword leaks
    assert isinstance(body["similar"], list)
    assert isinstance(body["matches"], list)
    if body["matches"]:
        m = body["matches"][0]
        assert m["breakdown"]["text_similarity"] is not None
        assert "reason" in m


def test_public_summary(client):
    r = client.get("/api/stats/summary")
    assert r.status_code == 200
    s = r.json()
    assert s["total_problems"] >= 20
