"""HTTP routers for the AP2WEB API.

Fase 2.2: o monolíito ``main.py`` foi decomposto aqui. Cada submódulo expõe um
``APIRouter`` (ou registradores equivalentes) que ``main.py`` anexa ao app —
o app, o lifespan, os handlers de exceção e o middleware continuam em
``main.py`` porque são objetos de aplicação, não de rota.
"""
