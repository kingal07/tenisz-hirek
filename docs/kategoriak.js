// Női / férfi / páros besorolás szabályai. Bővíthető: új név vagy kulcsszó a megfelelő listába.
// A neveknél számít a kis- és nagybetű, és a toldalékos alakokat is felismeri (pl. "Sabalenkát").
window.KATEGORIAK = {
  // Forrás (hírforrás vagy YouTube-csatorna neve) -> alapértelmezett kategória
  forras: {
    'ATP Tour': 'ferfi', 'Tennis TV': 'ferfi', 'Laver Cup': 'ferfi', 'Jannik Sinner': 'ferfi',
    'WTA': 'noi', 'Billie Jean King Cup': 'noi'
  },
  // Ezeknél a forrás mindent eldönt (csak férfi vagy csak női tartalom van rajtuk)
  csakForras: ['ATP Tour', 'Tennis TV', 'Laver Cup', 'Jannik Sinner', 'WTA', 'Billie Jean King Cup'],

  noiSzavak: ["women's", 'women', 'woman', 'ladies', 'wta', 'női', 'nők', 'nőknél', 'nőket', 'hölgy',
    'billie jean', 'bjk', 'fed cup', 'girls'],
  ferfiSzavak: ["men's", 'men', 'atp', 'férfi', 'férfiak', 'férfiaknál', 'davis cup', 'davis-kupa', 'davis-kupában',
    'davis-kupát', 'laver cup', 'next gen', 'boys'],
  parosSzavak: ['doubles', 'páros', 'párosban', 'párost', 'párosok', 'párosa', 'párosát', 'párosverseny', 'duó', 'duója'],
  vegyesSzavak: ['mixed doubles', 'mixed-doubles', 'vegyes páros', 'vegyespáros', 'vegyes párosban', 'vegyes párost'],

  noiNevek: ['Sabalenka', 'Swiatek', 'Świątek', 'Gauff', 'Rybakina', 'Pegula', 'Keys', 'Andreeva', 'Paolini',
    'Qinwen', 'Navarro', 'Badosa', 'Muchova', 'Muchová', 'Svitolina', 'Kostyuk', 'Noskova', 'Nosková', 'Mboko',
    'Anisimova', 'Alexandrova', 'Samsonova', 'Kasatkina', 'Ostapenko', 'Krejcikova', 'Krejčíková', 'Vondrousova',
    'Vondroušová', 'Kvitova', 'Kvitová', 'Jabeur', 'Osaka', 'Raducanu', 'Leylah', 'Tauson', 'Haddad Maia',
    'Kalinskaya', 'Shnaider', 'Mertens', 'Siniakova', 'Siniaková', 'Townsend', 'Errani', 'Kudermetova',
    'Dabrowski', 'Routliffe', 'Hsieh', 'Stearns', 'Danielle Collins', 'Azarenka', 'Bencic', 'Pliskova', 'Plíšková',
    'Linette', 'Frech', 'Putintseva', 'Bouzkova', 'Sakkari', 'Caroline Garcia', 'Wozniacki', 'Serena', 'Venus',
    'Barty', 'Halep', 'Kerber', 'Sharapova', 'Udvardy', 'Bondár', 'Bondar', 'Gálfi', 'Galfi', 'Stollár', 'Stollar',
    'Jani Réka', 'Babos', 'Joint', 'Eala', 'Fruhvirtova', 'Kenin', 'Bouzas', 'Jovic', 'Starodubtseva', 'Boisson',
    'Cirstea', 'Bejlek', 'Eva Lys', 'Tomljanovic', 'Kessler', 'Krueger', 'Parks', 'Zheng', 'Wang Xinyu', 'Yafan',
    'Shuai', 'Zvonareva', 'Mladenovic', 'Kichenok', 'Melichar', 'Aoyama', 'Shibahara', 'Ninomiya', 'Sorribes',
    'Bucsa', 'Kalinina', 'Yastremska', 'Sevastova', 'Golubic', 'Teichmann', 'Vekic', 'Vekić', 'Pavlyuchenkova',
    'Rakhimova', 'Potapova', 'Blinkova', 'Zakharova', 'Sasnovich', 'Vandeweghe', 'Navratilova', 'Evert', 'Graf'],

  ferfiNevek: ['Sinner', 'Alcaraz', 'Djokovic', 'Đoković', 'Zverev', 'Medvedev', 'Fritz', 'Draper', 'de Minaur',
    'De Minaur', 'Ruud', 'Rune', 'Musetti', 'Shelton', 'Tsitsipas', 'Tommy Paul', 'Rublev', 'Dimitrov', 'Hurkacz',
    'Khachanov', 'Lehecka', 'Menšík', 'Mensik', 'Fils', 'Humbert', 'Cerundolo', 'Tiafoe', 'Auger-Aliassime',
    'Shapovalov', 'Bublik', 'Machac', 'Fonseca', 'Jodar', 'Cobolli', 'Berrettini', 'Darderi', 'Kecmanovic',
    'Mpetshi', 'Michelsen', 'Nakashima', 'Korda', 'Learner Tien', 'Monfils', 'Wawrinka', 'Nadal', 'Federer',
    'Andy Murray', 'Kyrgios', 'Thiem', 'Fucsovics', 'Marozsán', 'Marozsan', 'Piros Zsombor', 'Valkusz', 'Nishikori',
    'Navone', 'Etcheverry', 'Struff', 'Davidovich', 'Popyrin', 'Griekspoor', 'Altmaier', 'Moutet', 'Báez', 'Baez',
    'Arnaldi', 'Sonego', 'Norrie', 'Dan Evans', 'Borges', 'Diallo', 'Cilic', 'Čilić', 'Opelka', 'Brooksby',
    'Kokkinakis', 'Jordan Thompson', 'Vukic', 'Mannarino', 'Bonzi', 'Bergs', 'Zeballos', 'Granollers', 'Arevalo',
    'Pavic', 'Krawietz', 'Puetz', 'Pütz', 'Bolelli', 'Vavassori', 'Salisbury', 'Skupski', 'Heliovaara', 'Patten',
    'Glasspool', 'Rajeev Ram', 'Purcell', 'Koolhof', 'Mektic', 'Dodig', 'Krajicek', 'Ebden', 'Molteni', 'Bopanna',
    'Roger-Vasselin', 'Doumbia', 'Reboul', 'Mahut', 'Herbert', 'Hijikata', 'Kubler', 'Thompson', 'Mmoh', 'Giron',
    'Djere', 'Halys', 'Gaston', 'Van de Zandschulp', 'Hanfmann', 'Koepfer', 'Zandschulp', 'Comesana', 'Prizmic',
    'Buse', 'Tabilo', 'Jarry', 'Garin', 'Kovacevic', 'Wong', 'Shang', 'Zhang Zhizhen', 'Bu Yunchaokete', 'Rinderknech',
    'Kopriva', 'Svajda', 'Basavareddy', 'Blockx', 'Engel', 'Stricker', 'Sampras', 'Agassi', 'Roddick', 'Becker',
    'Edberg', 'Lendl', 'McEnroe', 'Borg'],

  // "Név/Név" alakú cím (pl. "Granollers/Zeballos win") általában páros mérkőzés
  perJel: true
};
