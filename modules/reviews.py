"""6. Review module – ratings & comments (customers), moderation hook."""
from flask import Blueprint, abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Product, Review

bp = Blueprint("reviews", __name__)


@bp.route("/product/<int:product_id>/review", methods=["POST"])
@login_required
def submit(product_id):
    product = db.get_or_404(Product, product_id)
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()[:1000]
    back = url_for("products.product_detail", product_id=product_id) + "#reviews"
    if rating not in range(1, 6):
        flash("Pick a star rating from 1 to 5.", "error")
        return redirect(back)
    review = Review.query.filter_by(user_id=current_user.user_id, product_id=product_id).first()
    if review:
        review.rating, review.comment = rating, comment
        flash("Your review was updated.", "success")
    else:
        db.session.add(Review(user_id=current_user.user_id, product_id=product.product_id,
                              rating=rating, comment=comment))
        flash("Thanks! Your review is live.", "success")
    db.session.commit()
    return redirect(back)


@bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def delete(review_id):
    review = db.get_or_404(Review, review_id)
    if review.user_id != current_user.user_id and not current_user.is_admin:
        abort(403)
    pid = review.product_id
    db.session.delete(review)
    db.session.commit()
    flash("Review deleted.", "info")
    if current_user.is_admin and request.form.get("from_admin"):
        return redirect(url_for("admin.reviews"))
    return redirect(url_for("products.product_detail", product_id=pid) + "#reviews")
