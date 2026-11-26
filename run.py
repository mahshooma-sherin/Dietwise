"""
DietWise Unified Server:
Serves both the React frontend and the FastAPI backend from a single unified server.
"""
import os
import sys
import subprocess
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"
DIST_DIR = FRONTEND_DIR / "dist"

def ensure_frontend_built():
    index_file = DIST_DIR / "index.html"
    if not index_file.exists() or "--build" in sys.argv:
        print("[DietWise] Building React frontend bundle...")
        subprocess.run("npm run build", cwd=FRONTEND_DIR, shell=True, check=True)
        print("[DietWise] Frontend build complete.")

def main():
    ensure_frontend_built()
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    
    # Ensure backend modules can be imported
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    
    os.environ["FRONTEND_DIST"] = str(DIST_DIR)
    
    url = f"http://localhost:{port}" if host in ("127.0.0.1", "0.0.0.0") else f"http://{host}:{port}"
    print(f"[DietWise] Serving full application on {url}")
    print(f"[DietWise] Web UI:   {url}/")
    print(f"[DietWise] API docs: {url}/docs")
    
    if "--no-open" not in sys.argv:
        try:
            webbrowser.open(url)
        except Exception:
            pass
            
    import uvicorn
    uvicorn.run("app.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
