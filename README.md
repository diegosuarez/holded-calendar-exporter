# Exportador de calendario de Holded.
Holded. Ese unicornio español que ha levantado más de 200 millones en financiación, tiene decenas de ingenieros trabajando en el producto y parece ser que nadie al volante en el equipo de API. Bastante grave es que en 2025 no sean API first y su web use una extraña mezcla de API y SSR, pero es que ni siquiera son coherentes entre las funcionalidades que ofrecen en el dashboard y las que ofrecen en la API; toda la funcionalidad de RRHH no está disponible via API.

Una de las funcionalides que se les lleva pidiendo desde 2021 es la capacidad de exportar calendarios a ICS/google calendar (https://feedback.holded.com/mejoras/p/que-fuera-posible-vincular-el-calendar-de-team-con-ausencias-del-equipo-al-calen). Una funcionalidad que lleva literamente media hora de desarrollo teniendo acceso al código/BBDD (y lo sé porque a mí me ha llevado dos, teniendo que descifrar el SSR y sin conocer la API), pero que no les da la gana de implementar.

Para cualquiera que le pueda venir bien, aquí dejo un script de Python que "accede" a Holded, se descarga el calendario de ausencias del equipo, lo exporta a un .ICS en local y lo sube a Google Calendar mediante la API de google. Para los requisitos, basta un `pip install google-api-python-client google-auth icalendar beautifulsoup4 requests jq`. 

Para ejecutarlo, toma el mes y el año que se quiere sincronizar. (`python sync-calendar.py 05 2025`) Como el 2FA es obligatorio, al intentar logarse te pedirá el código 2FA que manda holded al correo.

Puede ejecutarse varias veces, puesto que en los eventos exportados se incluye un iCalUID para no repetir eventos. Si alguien quiere modificar el script para sincronizar todo el año de una tacada, las PR están abiertas. 
