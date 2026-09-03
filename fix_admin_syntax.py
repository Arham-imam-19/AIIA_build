import re

with open('frontend/src/dashboards/Admin.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# I will just re-fetch the original from git if possible? No, it's not a git repo maybe?
# I'll just fix the specific mangled lines!

content = content.replace(
    "className={px-5 py-3 text-[11px] font-bold uppercase tracking-wider }",
    "className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wider ${activeTab === 'governance' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}",
    1
)

content = content.replace(
    "className={px-5 py-3 text-[11px] font-bold uppercase tracking-wider }",
    "className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wider ${activeTab === 'personnel' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}",
    1
)

content = content.replace(
    "className={px-5 py-3 text-[11px] font-bold uppercase tracking-wider }",
    "className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wider ${activeTab === 'advanced' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}",
    1
)

content = content.replace(
    "{u.site_id ? siteMap[u.site_id] || Site # : 'Global (Multi-Centric)'}",
    "{u.site_id ? siteMap[u.site_id] || `Site #${u.site_id}` : 'Global (Multi-Centric)'}"
)

# And check for the URL qStr in api.js? Wait, api.js wasn't modified!
# What about the fetchUsers endpoint query string? We didn't touch fetchUsers!

with open('frontend/src/dashboards/Admin.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
