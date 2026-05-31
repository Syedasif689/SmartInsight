from pathlib import Path
path = Path('app/__init__.py')
text = path.read_text()
needle = '    return app'
replace = '''    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        app.logger.exception("Unhandled exception")

        if request.is_json:
            return jsonify({"error": "An unexpected error occurred."}), 500

        return render_template(
            "dashboard.html",
            dashboard=None,
            error="An unexpected error occurred. Please try again.",
        ), 500

    return app'''
if needle not in text:
    raise SystemExit('needle not found')
path.write_text(text.replace(needle, replace))
print('patched')
