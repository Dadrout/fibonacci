-- Reviewed, original fact notes with source links (not copied source text).
-- Safe to re-run: updates the canonical seed entries in place.
insert into public.knowledge_entries
  (subject, canonical_topic, aliases, grade_bands, facts, sources, reviewed_at, is_approved)
values
  (
    'history', 'The Silk Road',
    array['Silk Road', 'Silk Roads', 'How the Silk Road connected people', 'Шёлковый путь', 'Шелковый путь'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'The Silk Roads were a network of land and sea routes linking societies across Asia and beyond, rather than one single road.',
      'Silk was an important trade good, but merchants also moved textiles, spices, horses, glass, ceramics, and other goods.',
      'Travel and trade along these routes helped ideas, religions, languages, scientific knowledge, and technologies move between communities.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'About the Silk Roads', 'publisher', 'UNESCO',
      'url', 'https://www.unesco.org/en/silk-roads/about-silk-roads'
    )), now(), true
  ),
  (
    'history', 'Ancient Egypt',
    array['Egypt', 'Ancient Egyptian civilization', 'Pyramids of Egypt', 'Древний Египет', 'пирамиды Египта'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'The Old Kingdom was a major period of pyramid building; the pyramids of Khufu, Khafre, and Menkaure were built at Giza.',
      'The Step Pyramid of Djoser at Saqqara was an early major stone monument and an important step in pyramid architecture.',
      'Archaeologists learn about ordinary people as well as rulers from objects and remains found in Egyptian tombs.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Egypt in the Old Kingdom', 'publisher', 'The Metropolitan Museum of Art',
      'url', 'https://www.metmuseum.org/essays/egypt-in-the-old-kingdom-ca-2649-2150-b-c'
    ), jsonb_build_object(
      'title', 'Egyptian Tombs: Life Along the Nile', 'publisher', 'The Metropolitan Museum of Art',
      'url', 'https://www.metmuseum.org/essays/egyptian-tombs-life-along-the-nile'
    )), now(), true
  ),
  (
    'history', 'The First Cities',
    array['First cities', 'Uruk', 'Early Mesopotamian cities', 'первые города', 'Урук', 'древние города Месопотамии'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Uruk in southern Mesopotamia became one of the earliest large urban centers known to archaeologists.',
      'Archaeological remains from early Mesopotamian cities include monumental buildings, organized neighborhoods, and evidence of specialized work.',
      'Clay tablets and seal impressions helped people record and authenticate goods, work, and exchanges.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'The Uruk Period', 'publisher', 'Penn Museum',
      'url', 'https://www.penn.museum/sites/bulletin/2600/'
    ), jsonb_build_object(
      'title', 'Traders of the Mountains', 'publisher', 'Penn Museum',
      'url', 'https://www.penn.museum/sites/expedition/traders-of-the-mountians/'
    )), now(), true
  ),
  (
    'history', 'The Roman Empire',
    array['Ancient Rome', 'Rome', 'Roman roads', 'Roman Empire roads and trade', 'Римская империя', 'Древний Рим'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'The Roman Empire connected lands and communities across Europe, North Africa, and western Asia for centuries.',
      'Roman roads linked settlements, military outposts, and provinces; soldiers helped build and maintain many roads.',
      'Romans also used the Mediterranean Sea and navigable rivers to move people and goods.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Large print guide: Legion, life in the Roman army', 'publisher', 'British Museum',
      'url', 'https://www.britishmuseum.org/exhibitions/legion-life-roman-army/large-print-guide'
    ), jsonb_build_object(
      'title', 'Introduction to ancient Rome', 'publisher', 'British Museum',
      'url', 'https://www.britishmuseum.org/exhibitions/nero-man-behind-myth/introduction-to-ancient-rome'
    )), now(), true
  ),
  (
    'history', 'The Printing Press',
    array['Gutenberg', 'Gutenberg printing press', 'The Gutenberg Bible', 'printing history', 'печатный станок', 'Гутенберг'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Printing existed in East Asia before Johannes Gutenberg developed a press using movable metal type in Europe.',
      'The Gutenberg Bible was among the first major books printed in Western Europe with movable metal type and was probably completed in Mainz around 1455.',
      'Movable type made it possible to print many consistent copies of a page, changing how books could be produced and shared.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'The Gutenberg Bible', 'publisher', 'Library of Congress',
      'url', 'https://www.loc.gov/exhibits/bibles/the-gutenberg-bible.html'
    ), jsonb_build_object(
      'title', 'Johannes Gutenberg (c.1400–1468)', 'publisher', 'Library of Congress',
      'url', 'https://guides.loc.gov/gutenberg/the-printer'
    )), now(), true
  ),
  (
    'geography', 'How Mountains Form',
    array['Mountains', 'Mountain formation', 'How the Himalayas formed', 'горы', 'образование гор', 'как образовались Гималаи'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Many mountain ranges form where tectonic plates push together and force sections of Earth’s crust upward.',
      'The Himalayas began forming when the Indian Plate collided with the Eurasian Plate tens of millions of years ago.',
      'Mountains continue to change as uplift, earthquakes, rivers, glaciers, and weathering reshape them.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'The Himalayas: Two Continents Collide', 'publisher', 'U.S. Geological Survey',
      'url', 'https://pubs.usgs.gov/gip/dynamic/himalaya.html'
    ), jsonb_build_object(
      'title', 'Understanding Plate Motions', 'publisher', 'U.S. Geological Survey',
      'url', 'https://pubs.usgs.gov/gip/dynamic/understanding.html'
    )), now(), true
  ),
  (
    'geography', 'The World’s Major Rivers',
    array['Major rivers', 'World rivers', 'Longest rivers', 'реки мира', 'крупнейшие реки мира', 'самые длинные реки'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Rivers provide fresh water and support ecosystems, farms, transport, and settlements.',
      'The Nile, Amazon, and Yangtze are among the world’s longest rivers, though exact rankings depend on how river sources and branches are measured.',
      'A river’s watershed is the land area that drains water into that river and its tributaries.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Rivers of the World: World’s Longest Rivers', 'publisher', 'U.S. Geological Survey',
      'url', 'https://www.usgs.gov/water-science-school/science/rivers-world-worlds-longest-rivers'
    ), jsonb_build_object(
      'title', 'Water World', 'publisher', 'U.S. Geological Survey',
      'url', 'https://www.usgs.gov/educational-resources/water-world'
    )), now(), true
  ),
  (
    'geography', 'Why Climates Differ',
    array['Climate', 'Climate differences', 'What affects climate', 'климат', 'почему климат отличается', 'что влияет на климат'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Climate describes the long-term patterns of temperature, precipitation, and other weather conditions in a place.',
      'Latitude changes the amount of solar energy a region receives; elevation, nearby water, winds, and mountains also affect climate.',
      'Ocean currents move heat around the planet and can make nearby coastal regions warmer or cooler.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'What Is Climate?', 'publisher', 'National Oceanic and Atmospheric Administration',
      'url', 'https://www.gml.noaa.gov/infodata/info_activities/pdfs/TBI_what_is_climate.pdf'
    ), jsonb_build_object(
      'title', 'How Does the Ocean Affect Climate and Weather on Land?', 'publisher', 'NOAA Ocean Exploration',
      'url', 'https://oceanexplorer.noaa.gov/ocean-fact/climate/'
    )), now(), true
  ),
  (
    'geography', 'The Water Cycle',
    array['Water cycle', 'Where rain comes from', 'How water moves around Earth', 'круговорот воды', 'откуда берется дождь'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'The Sun supplies much of the energy that drives evaporation and the movement of water through the water cycle.',
      'Water vapor cools and condenses into tiny droplets that form clouds; water later falls as precipitation such as rain or snow.',
      'Some precipitation flows over land into rivers, while some soaks into the ground and becomes groundwater.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Interactive Water Cycle Diagram for Kids', 'publisher', 'U.S. Geological Survey',
      'url', 'https://water.usgs.gov/edu/watercycle-kids-beg.html'
    )), now(), true
  ),
  (
    'geography', 'Tectonic Plates and Earth’s Surface',
    array['Plate tectonics', 'Tectonic plates', 'Earth plates', 'земная кора', 'тектонические плиты', 'движение плит'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Earth’s outer shell is divided into large plates that move slowly over geologic time.',
      'Where plates move apart, collide, or slide past one another, they can create earthquakes, volcanoes, and mountain building.',
      'Scientists use the patterns of earthquakes, volcanoes, and rock formations as evidence for plate motion.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'This Dynamic Earth: Understanding Plate Motions', 'publisher', 'U.S. Geological Survey',
      'url', 'https://pubs.usgs.gov/gip/dynamic/understanding.html'
    )), now(), true
  ),
  (
    'philosophy', 'Fairness and Justice',
    array['Fairness', 'Justice', 'What is fair?', 'What is justice?', 'справедливость', 'что такое справедливость'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Philosophers discuss justice in personal actions, laws, public policies, and the way societies are organized.',
      'Fairness can involve treating people equally, responding to different needs, or giving people what they are owed; philosophers debate how to balance these ideas.',
      'There is no single agreed theory of justice, so examples and reasons matter when comparing different views.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Justice', 'publisher', 'Stanford Encyclopedia of Philosophy',
      'url', 'https://plato.stanford.edu/entries/justice/'
    )), now(), true
  ),
  (
    'philosophy', 'What Is Truth?',
    array['Truth', 'How do we know what is true?', 'Theories of truth', 'истина', 'как узнать правду', 'теории истины'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Philosophers ask what makes a statement true and how truth relates to the world, evidence, and language.',
      'Correspondence, coherence, and pragmatic theories offer different ways to explain truth.',
      'These theories remain debated; a careful discussion should explain which view is being used rather than present one as settled.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Truth', 'publisher', 'Stanford Encyclopedia of Philosophy',
      'url', 'https://plato.stanford.edu/entries/truth/'
    )), now(), true
  ),
  (
    'philosophy', 'What Is Knowledge?',
    array['Knowledge', 'How do we know?', 'What does it mean to know something?', 'знание', 'как мы узнаем', 'что значит знать'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Knowing something is different from merely believing it, because a belief can be mistaken.',
      'A famous proposal describes knowledge as justified true belief, but philosophers have raised counterexamples and continue to debate what knowledge requires.',
      'Evidence, reasons, experience, and reliable ways of learning are all discussed in epistemology, the study of knowledge.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'The Analysis of Knowledge', 'publisher', 'Stanford Encyclopedia of Philosophy',
      'url', 'https://plato.stanford.edu/entries/knowledge-analysis/'
    )), now(), true
  ),
  (
    'philosophy', 'Making a Good Decision',
    array['Good decisions', 'What makes a good decision?', 'Choices and consequences', 'хорошее решение', 'как принять решение', 'выбор и последствия'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Decision theory studies how people choose among options and how beliefs, goals, and values can shape those choices.',
      'Some decisions involve risk, where possible outcomes and probabilities are known or estimated; others involve uncertainty.',
      'A thoughtful decision can compare possible outcomes while also recognizing that people may value outcomes differently.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Decision Theory', 'publisher', 'Stanford Encyclopedia of Philosophy',
      'url', 'https://plato.stanford.edu/entries/decision-theory/'
    )), now(), true
  ),
  (
    'philosophy', 'What Is a Good Life?',
    array['The good life', 'Happiness and virtue', 'What makes life meaningful?', 'хорошая жизнь', 'счастье и добродетель', 'что делает жизнь хорошей'],
    array['10-12', '13-15', '16-18'],
    jsonb_build_array(
      'Aristotle connected a good human life with well-being and excellent activity, not only with feeling pleasure.',
      'Virtue ethics emphasizes qualities of character such as courage, honesty, and practical wisdom.',
      'Philosophers disagree about what makes a life go well, and different traditions offer different answers.'
    ),
    jsonb_build_array(jsonb_build_object(
      'title', 'Aristotle’s Ethics', 'publisher', 'Stanford Encyclopedia of Philosophy',
      'url', 'https://plato.stanford.edu/entries/aristotle-ethics/'
    ), jsonb_build_object(
      'title', 'Virtue Ethics', 'publisher', 'Stanford Encyclopedia of Philosophy',
      'url', 'https://plato.stanford.edu/entries/ethics-virtue/'
    )), now(), true
  )
on conflict (subject, canonical_topic) do update set
  aliases = excluded.aliases,
  grade_bands = excluded.grade_bands,
  facts = excluded.facts,
  sources = excluded.sources,
  reviewed_at = excluded.reviewed_at,
  is_approved = excluded.is_approved;
