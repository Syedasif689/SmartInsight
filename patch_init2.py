from pathlib import Path
p = Path("app/__init__.py")
text = p.read_text()
dup = '''    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        app.logger.exception("Unhandled exception")

        if request.is_json:
            return jsonify({"error": "An unexpected error occurred."}), 500

        return render_template(
            "dashboard.html",
            dashboard=None,
            error="An unexpected error occurred. Please try again.",
        ), 500

    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        app.logger.exception("Unhandled exception")

        if request.is_json:
            return jsonify({"error": "An unexpected error occurred."}), 500

        return render_template(
            "dashboard.html",
            dashboard=None,
            error="An unexpected error occurred. Please try again.",
        ), 500
'''
keep = '''    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        app.logger.exception("Unhandled exception")

        if request.is_json:
            return jsonify({"error": "An unexpected error occurred."}), 500

        return render_template(
            "dashboard.html",
            dashboard=None,
            error="An unexpected error occurred. Please try again.",
        ), 500
'''
if dup not in text:
    raise SystemExit('duplicate not found')
text = text.replace(dup, keep, 1)
p.write_text(text)
print('fixed')
