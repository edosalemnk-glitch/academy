    return render_template("exam_result.html", course=course, exam=attempt, cert=cert)


@app.route("/terrain-sql", methods=["GET", "POST"])
@login_required
def sql_lab():
    course_id = request.values.get("course_id", type=int)
    if not course_id:
        flash("Le Terrain SQL est accessible depuis le cours SQL concerné.", "info")
        return redirect(url_for("my_courses"))

    course = get_course(course_id)
    if "SQL" not in course["title"].upper() and course["category"] != "SQL":
        abort(404)
    mode = course_access(course)

    challenge_id = request.form.get("challenge", type=int) or request.args.get("defi", type=int)
    default_sql = "SELECT " if request.args.get("defi") else "SELECT * FROM employes;"
    sql = request.form.get("sql", default_sql)
    result, error, verdict = None, None, None
    if request.method == "POST":
        try:
            cols, rows, truncated = sqllab.run_query(sql)
            result = {"cols": cols, "rows": rows, "truncated": truncated}
            if challenge_id:
                verdict = sqllab.check_challenge(challenge_id, rows)
        except sqllab.LabError as exc:
            error = str(exc)
    return render_template("sql_lab.html", sql=sql, result=result, error=error, verdict=verdict,
                           challenge_id=challenge_id, tables=sqllab.TABLES, challenges=sqllab.CHALLENGES,
                           max_rows=sqllab.MAX_ROWS, course=course, mode=mode)


# ------------------------------------------------------------------ espace formateur
@app.route("/formateur")
@trainer_required