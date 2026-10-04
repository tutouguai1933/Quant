set -e
cd /home/djy/Quant
QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 /home/djy/.npm-global/bin/pnpm --dir apps/web exec playwright test tests/ui-home-equity.spec.cjs tests/ui-home-three-numbers.spec.cjs --reporter=line > docs/research/2026-10-04-balance-private/home-final.log 2>&1
tail -8 docs/research/2026-10-04-balance-private/home-final.log
