#!/bin/bash
# Opportunity analyzer - identifies trading opportunities in prediction markets

TIMESTAMP=$(date -Iseconds)
DATE=$(date +%Y-%m-%d)
DATA_DIR="market-data"
ANALYSIS_FILE="$DATA_DIR/opportunity-analysis-$DATE.txt"

# Ensure we're in logs directory
cd "$(dirname "$0")" || exit 1

mkdir -p "$DATA_DIR"

echo "=== Market Opportunity Analysis: $DATE ===" > "$ANALYSIS_FILE"
echo "Generated: $TIMESTAMP" >> "$ANALYSIS_FILE"
echo "" >> "$ANALYSIS_FILE"

# Get top 20 markets for analysis
echo "SCANNING TOP 20 MARKETS FOR OPPORTUNITIES..." >> "$ANALYSIS_FILE"
echo "=============================================" >> "$ANALYSIS_FILE"

# Get top markets data
TOP_MARKETS=$(polymarket --top --limit=20 2>&1 | tail -n +3)

# Analyze each market for opportunities
echo "$TOP_MARKETS" | while IFS= read -r line; do
    if [[ "$line" =~ Yes:\ ([0-9.]+)% ]]; then
        yes_prob="${BASH_REMATCH[1]}"
        
        # Extract volume
        volume=""
        if [[ "$line" =~ 24h:\ \$([0-9,]+) ]]; then
            volume="${BASH_REMATCH[1]}"
            # Remove commas from volume for numeric comparison
            volume_num=$(echo "$volume" | tr -d ',')
        fi
        
        # Check for opportunities based on criteria
        opportunity=""
        
        # Criteria 1: Balanced markets (40-60% probability) with high volume
        if (( $(echo "$yes_prob >= 40 && $yes_prob <= 60" | bc -l 2>/dev/null) )); then
            if [[ -n "$volume_num" ]] && (( volume_num > 1000000 )); then
                opportunity="BALANCED_HIGH_VOLUME"
            elif [[ -n "$volume_num" ]] && (( volume_num > 500000 )); then
                opportunity="BALANCED_MEDIUM_VOLUME"
            fi
        
        # Criteria 2: Extreme probabilities with very high volume (contrarian plays)
        elif (( $(echo "$yes_prob <= 10 || $yes_prob >= 90" | bc -l 2>/dev/null) )); then
            if [[ -n "$volume_num" ]] && (( volume_num > 2000000 )); then
                opportunity="EXTREME_HIGH_VOLUME"
            fi
        
        # Criteria 3: Medium probabilities with very high volume
        elif (( $(echo "($yes_prob >= 25 && $yes_prob <= 35) || ($yes_prob >= 65 && $yes_prob <= 75)" | bc -l 2>/dev/null) )); then
            if [[ -n "$volume_num" ]] && (( volume_num > 3000000 )); then
                opportunity="MEDIUM_EXTREME_HIGH_VOLUME"
            fi
        fi
        
        if [[ -n "$opportunity" ]]; then
            echo "" >> "$ANALYSIS_FILE"
            echo "OPPORTUNITY DETECTED: $opportunity" >> "$ANALYSIS_FILE"
            echo "Market: $line" >> "$ANALYSIS_FILE"
            echo "Yes Probability: ${yes_prob}%" >> "$ANALYSIS_FILE"
            echo "24h Volume: \$$volume" >> "$ANALYSIS_FILE"
            
            # Add recommendation based on opportunity type
            case "$opportunity" in
                BALANCED_HIGH_VOLUME)
                    echo "Recommendation: Strong opportunity - balanced market with high liquidity" >> "$ANALYSIS_FILE"
                    echo "Risk: Medium | Potential: High" >> "$ANALYSIS_FILE"
                    ;;
                BALANCED_MEDIUM_VOLUME)
                    echo "Recommendation: Good opportunity - balanced market with decent liquidity" >> "$ANALYSIS_FILE"
                    echo "Risk: Medium | Potential: Medium" >> "$ANALYSIS_FILE"
                    ;;
                EXTREME_HIGH_VOLUME)
                    echo "Recommendation: Contrarian play - extreme probability with high volume" >> "$ANALYSIS_FILE"
                    echo "Risk: High | Potential: Very High" >> "$ANALYSIS_FILE"
                    ;;
                MEDIUM_EXTREME_HIGH_VOLUME)
                    echo "Recommendation: Momentum play - leaning probability with very high volume" >> "$ANALYSIS_FILE"
                    echo "Risk: Medium-High | Potential: High" >> "$ANALYSIS_FILE"
                    ;;
            esac
        fi
    fi
done

# Check if no opportunities found
if ! grep -q "OPPORTUNITY DETECTED" "$ANALYSIS_FILE"; then
    echo "" >> "$ANALYSIS_FILE"
    echo "NO STRONG OPPORTUNITIES FOUND IN TOP 20 MARKETS" >> "$ANALYSIS_FILE"
    echo "Recommendation: Wait for better market conditions or expand search" >> "$ANALYSIS_FILE"
fi

# Add market summary
echo "" >> "$ANALYSIS_FILE"
echo "MARKET SUMMARY:" >> "$ANALYSIS_FILE"
echo "===============" >> "$ANALYSIS_FILE"
total_markets=$(echo "$TOP_MARKETS" | grep -c "Yes:")
echo "Total markets analyzed: $total_markets" >> "$ANALYSIS_FILE"

# Count by probability ranges
low_prob=$(echo "$TOP_MARKETS" | grep -E "Yes: ([0-9]{1,2}\.[0-9]|100\.0)%" | grep -E "Yes: (0\.|1\.|2\.|3\.|4\.|[0-9]\.|10\.|11\.|12\.|13\.|14\.|15\.|16\.|17\.|18\.|19\.|20\.|21\.|22\.|23\.|24\.|25\.|26\.|27\.|28\.|29\.|30\.)" | wc -l)
medium_prob=$(echo "$TOP_MARKETS" | grep -E "Yes: (3[1-9]|4[0-9]|5[0-9]|6[0-9])\.([0-9])%" | wc -l)
high_prob=$(echo "$TOP_MARKETS" | grep -E "Yes: (7[0-9]|8[0-9]|9[0-9]|100\.0)%" | wc -l)

echo "Low probability (<31%): $low_prob markets" >> "$ANALYSIS_FILE"
echo "Medium probability (31-69%): $medium_prob markets" >> "$ANALYSIS_FILE"
echo "High probability (>69%): $high_prob markets" >> "$ANALYSIS_FILE"

# Volume analysis
total_volume=$(echo "$TOP_MARKETS" | grep -oE "24h: \$[0-9,]+" | sed 's/[^0-9,]//g' | tr -d ',' | paste -sd+ | bc 2>/dev/null || echo "0")
if [[ "$total_volume" -gt 0 ]]; then
    total_volume_formatted=$(printf "%'.0f" "$total_volume")
    echo "Total 24h volume in top 20: \$$total_volume_formatted" >> "$ANALYSIS_FILE"
fi

echo "" >> "$ANALYSIS_FILE"
echo "ANALYSIS COMPLETED: $TIMESTAMP" >> "$ANALYSIS_FILE"
echo "=================================" >> "$ANALYSIS_FILE"

echo "Opportunity analysis saved to: $ANALYSIS_FILE"