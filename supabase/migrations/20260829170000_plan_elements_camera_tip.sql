-- CAMERE DE SUPRAVEGHERE: tipul camerei (Bullet / Dome / Turret / PTZ / Fisheye 180 / Fisheye 360 /
-- Termica). Unghiul si raza conului de acoperire vin din TIP, deci tipul trebuie sa fie un camp
-- propriu, nu o bucata dintr-un alt camp.
--
-- DE CE COLOANA NOUA si nu `label`: `label` poarta deja montajul ("interior"/"exterior") si e citit
-- ca atare in mai multe locuri (`_cs_abbr_for` compara `label == "exterior"`, BOM-ul si legenda la
-- fel). Un `label` compus de forma "exterior|bullet" ar rupe TACUT toate comparatiile alea — fiecare
-- camera de exterior ar fi devenit CV-INT. Exact clasa de esec tacut de evitat.
--
-- ORIENTAREA conului NU cere coloana: se scrie in `rotation` (real NOT NULL DEFAULT 0), care exista
-- deja si e folosita la fel de prize si intrerupatoare.
--
-- Coloana e text NULLABIL, FARA constraint: proiectele existente raman cu NULL, iar codul le trateaza
-- ca Dome (tipul cel mai uzual la interior). Migratie aditiva pura — nicio linie atinsa.
--
-- ORDINE DE APLICARE (Dan): migratia INAINTE de deploy, ca la toate celelalte. Codul nou selecteaza
-- coloana explicit (SELECT_COLS), deci fara ea editorul n-ar mai citi niciun element.

alter table public.plan_elements
  add column if not exists camera_tip text;

comment on column public.plan_elements.camera_tip is
  'Tipul camerei de supraveghere (bullet/dome/turret/ptz/fisheye180/fisheye360/termica). Da unghiul si raza conului de acoperire. NULL pe elementele care nu-s camere si pe camerele vechi (tratate ca dome). Montajul interior/exterior ramane in `label`; orientarea conului in `rotation`.';
