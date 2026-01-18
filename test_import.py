import sys
from pathlib import Path

# 添加src到路径
project_root = Path(__file__).parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

try:
    print("Testing imports...")

    # 测试 V2 导入
    print("1. Importing V2 state...")
    from agents.deep_research.v2.state import AgentState
    print("   ✓ state OK")

    print("2. Importing V2 tools...")
    from agents.deep_research.v2.tools import ConductResearch
    print("   ✓ tools OK")

    print("3. Importing V2 prompts...")
    from agents.deep_research.v2.prompts import SUPERVISOR_SYSTEM_PROMPT
    print("   ✓ prompts OK")

    print("4. Importing V2 researcher...")
    from agents.deep_research.v2.researcher import Researcher
    print("   ✓ researcher OK")

    print("5. Importing V2 supervisor...")
    from agents.deep_research.v2.supervisor import SupervisorAgent
    print("   ✓ supervisor OK")

    print("6. Importing V2 orchestrator...")
    from agents.deep_research.v2.orchestrator_v2 import DeepResearchV2
    print("   ✓ orchestrator OK")

    print("7. Importing main V2 package...")
    from agents.deep_research.v2 import DeepResearchV2 as V2
    print("   ✓ V2 package OK")

    print("\nAll imports successful!")

except Exception as e:
    print(f"\n❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
