.PHONY: run test ui-test eval eval-quick samples seed verify release docker
run:        ; HL_SEED_DEMO=1 python -m hairline.server
test:       ; python -m unittest discover -s tests -t . -v
ui-test:    ; python tests/record_ui_fixtures.py .ui_fixtures && for w in anon res eng; do WHO=$$w node tests/ui_smoke.js .ui_fixtures || exit 1; done
verify:     ; python scripts/verify_opencv5.py
samples:    ; python scripts/make_samples.py && python scripts/make_gauge_card.py
eval:       ; python scripts/run_eval.py
eval-quick: ; python scripts/run_eval.py --quick
release:    ; python scripts/make_release.py
docker:     ; docker build -t hairline . && docker run --rm -p 8080:8080 -e HL_SEED_DEMO=1 hairline
