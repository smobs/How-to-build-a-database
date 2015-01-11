import os, json, logging, cherrypy, collections
from blist import sorteddict
from flask import Flask, abort, request, make_response

class Database:
    def __init__(self, fields_to_index=[]):
        self.data = sorteddict()
        self.keys = self.data.keys()
        self.values = self.data.values()

        self.indexes = { field: sorteddict() for field in fields_to_index }

    def put(self, key, value):
        old_value = self.data[key] if key in self.data else None
        self.data[key] = value

        if isinstance(value, collections.Iterable):
            for field_name, index in self.indexes.items():
                self._update_index(index, field_name, value, old_value)

    def _update_index(self, index, field_name, new_value, old_value):
        if old_value:
            try:
                old_key_in_index = old_value[field_name]
                del index[old_key_in_index]
            except (KeyError, TypeError):
                pass
        try:
            key_in_index = new_value[field_name]
            index[key_in_index] = new_value
        except (KeyError, TypeError):
            pass

    def get(self, key):
        return self.data[key]

    def get_range(self, start_key, end_key):
        start_index = self.keys.bisect_left(start_key)
        end_index = self.keys.bisect_right(end_key)

        return self.values[start_index:end_index]

    def get_by(self, field_name, field_value):
        if field_name not in self.indexes:
            raise ValueError("Cannot query without an index for field %s" % field_name)

        index = self.indexes[field_name]
        return index[field_value]

    def sum(self, field_name):
        total = 0
        for value in self.values:
            try:
                total += value[field_name]
            except (KeyError, TypeError):
                pass
        return total

    def clear(self):
        self.data.clear()
        for index in self.indexes.values():
            index.clear()

def build_app():
  app = Flask(__name__)
  app.debug = True

  database = Database(["name"])

  @app.route("/reset", methods=["POST"])
  def reset():
      database.clear()
      return make_response("", 200)

  @app.route("/<int:item_id>", methods=["GET"])
  def get_item(item_id):
    try:
      return json.dumps(database.get(item_id))
    except KeyError:
      raise abort(404)

  @app.route("/range")
  def get_range():
    start, end = int(request.args.get('start')), int(request.args.get('end'))
    return json.dumps(database.get_range(start, end))

  @app.route("/<int:item_id>", methods=["POST"])
  def post_item(item_id):
    value = json.loads(request.data.decode('utf-8'))
    database.put(item_id, value)
    return make_response(str(value), 201)

  @app.route("/", methods=["POST"])
  def post_items():
      for k, v in json.loads(request.data.decode('utf-8')):
          database.put(k, v)
      return make_response("", 201)

  @app.route("/by/<field_name>/<field_value>")
  def query_by_field(field_name, field_value):
    parsed_value = json.loads(field_value)
    try:
        return json.dumps(database.get_by(field_name, parsed_value))
    except KeyError:
        raise abort(404)

  @app.route("/sum/<field_name>")
  def sum(field_name):
    return make_response(str(database.sum(field_name)), 200)

  return app

def run_server(app):
    cherrypy.tree.graft(app, '/')

    cherrypy.config.update({
        'server.socket_port': int(os.environ.get('PORT', '8080')),
        'server.socket_host': '0.0.0.0'
    })
    cherrypy.log.error_log.setLevel(logging.WARNING)

    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == '__main__':
    app = build_app()
    run_server(app)
