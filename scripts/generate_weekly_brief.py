import asyncio
import os
from src.ai.navigation.ai_navigator import AINavigator
from src.ai.navigation.brief_generator import BriefGenerator
from src.ai.navigation.sources import NewsIngestor

async def main():
    print("🚀 Initializing AI Navigation System...")
    navigator = AINavigator()
    generator = BriefGenerator()
    ingestor = NewsIngestor()

    print("🌐 Fetching Real Intelligence from RSS Feeds...")
    raw_news = await ingestor.get_latest_news()
    
    # 3. Deep Intelligence (New)
    print("💎 Ingesting Deep Intelligence Reports...")
    import json
    deep_path = "data/deep_intelligence.json"
    if os.path.exists(deep_path):
        with open(deep_path, 'r') as f:
            deep_news = json.load(f)
            raw_news.extend(deep_news)
            print(f"   [DEEP] Added {len(deep_news)} high-value reports.")

    if not raw_news:
        print("⚠️ No news fetched! Check connection or feeds.")
        return

    print(f"🔍 Analyzing {len(raw_news)} items...")
    for item in raw_news[:10]:
        print(f"   - [RAW] {item['title'][:60]}...")
    
    filtered = await navigator.filter_news(raw_news)
    
    print("💡 Generating Actionable Steps...")
    actions = await navigator.generate_actionable_steps(filtered)
    
    print("📝 Creating Visionary Brief...")
    markdown = generator.generate_markdown(filtered, actions)
    
    # Save to file
    report_path = "reports/weekly_brief_latest.md"
    os.makedirs("reports", exist_ok=True)
    with open(report_path, "w") as f:
        f.write(markdown)
    
    print(f"✅ Brief generated successfully: {report_path}")
    print("\n--- PREVIEW ---\n")
    print(markdown[:500] + "...")

if __name__ == "__main__":
    asyncio.run(main())
