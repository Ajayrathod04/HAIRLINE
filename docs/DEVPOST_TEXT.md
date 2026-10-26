# Devpost text (paste and edit; keep it true)

**Tagline:** Measure the crack. Know when to look again.

**Inspiration.** Cracks in old buildings are reported as words and unscaled photos, so nobody can tell a stable hairline from a growing one or prove a repair happened. We wanted a tool where the photo itself carries the measurement.

**What it does.** Print a 50 mm marker, stick it next to the crack, take a photo. HAIRLINE rectifies the wall with OpenCV and reports crack width in millimetres with an error bar. If the photo is not good enough (tilt, blur, glare, distance, missing marker) the agent refuses to measure and tells you exactly how to retake it. Serious or growing cracks become a review request for an engineer (never sent automatically). Closing needs engineer authorisation plus after-repair photo evidence; residents can dispute a closure; every action, including denials, is audited.

**How we built it.** OpenCV (marker detection, homography rectification, quality gates, black-hat segmentation, skeleton and distance-transform widths, visit-to-visit comparison) in a Python/Flask service on a Graviton EC2 instance behind CloudFront, with private S3, DynamoDB, Cognito and CloudWatch; an agent loop whose next action depends on the measurements, with an optional Bedrock planner kept inside a guardrail; a default-deny policy engine; a vanilla JS UI.

**Challenges.** Blur inflates thin cracks: our own benchmark caught that and caught our first fix over-correcting wide cracks, so we refit on separate seeds and report failure cases. White card paper tripped the glare gate; our first gauge card put lines outside the window. We kept those lessons in the docs.

**Accomplishments.** 46 tests plus a 144-scene benchmark with known widths: mean error 0.187 to 0.100 mm and p90 0.532 to 0.200 mm versus accepting every first photo; honest uncertainty (84% of errors inside the reported bar, 100% inside twice). Everything simulated is labelled simulated.

**What we learned.** Rejecting a bad photo is a feature. The marker as a shared coordinate frame makes change over time measurable without GPS.

**What's next.** Real-photo accuracy from the printed gauge card, live AWS CloudFormation deployment once credentials are authenticated, a pilot with one housing society or ward office, lens calibration, Verified Permissions.

**Built with.** OpenCV, Python, NumPy, scikit-image, Flask, gunicorn, Docker, Amazon EC2 (Graviton), CloudFront, S3, DynamoDB, Cognito, CloudWatch, (optional) Bedrock, CloudFormation.

**Responsible use.** Triage tool, not a structural certificate; demo cases simulated; uncertainty always shown; humans authorise every consequential step.
