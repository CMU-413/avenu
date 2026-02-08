from flask import Flask, request, jsonify
from flask_cors import CORS
from bson import ObjectId
from config import users_collection

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": ["http://localhost:5173"]}},
    supports_credentials=True,
)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"message": "HEALTH OK"}), 200

@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(force=True)

    if not data or "email" not in data:
        return jsonify({"error": "email is required"}), 400

    result = users_collection.insert_one(data)

    return jsonify({
        "id": str(result.inserted_id),
        "message": "user created",
    }), 201

@app.route("/users", methods=["GET"])
def get_users():
    users = []
    for user in users_collection.find():
        user["_id"] = str(user["_id"])
        users.append(user)

    return jsonify(users), 200

@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return jsonify({"error": "invalid user id"}), 400

    if not user:
        return jsonify({"error": "user not found"}), 404

    user["_id"] = str(user["_id"])
    return jsonify(user), 200

@app.route("/users/<user_id>", methods=["PUT"])
def update_user(user_id):
    data = request.get_json(force=True)

    if not data:
        return jsonify({"error": "no update payload provided"}), 400

    try:
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": data},
        )
    except Exception:
        return jsonify({"error": "invalid user id"}), 400

    if result.matched_count == 0:
        return jsonify({"error": "user not found"}), 404

    return jsonify({"message": "user updated"}), 200

@app.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        result = users_collection.delete_one(
            {"_id": ObjectId(user_id)}
        )
    except Exception:
        return jsonify({"error": "invalid user id"}), 400

    if result.deleted_count == 0:
        return jsonify({"error": "user not found"}), 404

    return jsonify({"message": "user deleted"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)