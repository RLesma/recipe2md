import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import recipe_to_md


MODERN_ELCOMIDISTA_HTML = """<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
[
  {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Curry verde tailandés",
    "author": {"@type": "Person", "name": "Mikel López Iturriaga"},
    "datePublished": "2021-10-07T17:14:34Z",
    "description": "Un curry rápido y aromático.",
    "recipeYield": "2 raciones",
    "prepTime": "PT15M",
    "cookTime": "PT20M",
    "totalTime": "PT35M"
  },
  {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    "thumbnailUrl": ["https://imagenes.elpais.com/preview.jpg"]
  }
]
</script>
</head>
<body>
<article>
  <div class="a_c clearfix" data-dtm-region="articulo_cuerpo">
    <p>Aunque la palabra curry se asocia a <a href="https://example.com/india">la India</a>, en <em>Tailandia</em> es maravilloso.</p>
    <figure><img src="https://imagenes.elpais.com/inline1.jpg" alt="Paso intermedio"/></figure>
    <div class="si">
      <div class="si_i">
        <div class="si_m">
          <h2 class="si_m_h">Ingredientes</h2>
          <h3 class="si_m_l_h dos">Para la base</h3>
          <ul>
            <li>150 g de ternera</li>
            <li>50 g de leche de coco</li>
          </ul>
          <h4 class="si_m_l_h nb">Emplatado</h4>
          <ul>
            <li>Cilantro fresco</li>
          </ul>
        </div>
      </div>
      <div class="si_d">
        <div class="si_m">
          <h2 class="si_m_h">Instrucciones</h2>
          <section class="si_m_p"><b class="si_m_p_num">1. </b><div class="si_m_p_div">Marcar la carne a fuego vivo.</div></section>
          <section class="si_m_p"><b class="si_m_p_num">2. </b><div class="si_m_p_div">Añadir la leche de coco y servir.</div></section>
        </div>
      </div>
    </div>
    <aside class="w w-sea">
      <figure><img src="https://imagenes.elpais.com/author.jpg" alt="Author"/></figure>
      <p>Texto del autor que no debe incluirse.</p>
    </aside>
  </div>
</article>
</body>
</html>
"""

QUIRKY_JSONLD_HTML = """<!DOCTYPE html>
<html>
<head>
<meta property="og:image" content="https://example.com/sangria.jpg">
<script type=application/ld+json class=yoast-schema-graph>
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Recipe",
      "name": "Sangría casera",
      "description": "Receta refrescante\ncon frutas.",
      "recipeIngredient": [
        "1 botella de vino tinto",
        "2 melocotones",
      ],
      "recipeInstructions": [
        {
          "@type": "HowToSection",
          "name": "Maceración",
          "itemListElement": [
            {"@type": "HowToStep", "text": "Cortar la fruta y mezclar con el vino."}
          ]
        }
      ],
    }
  ]
}
</script>
</head>
<body></body>
</html>
"""

LEGACY_ELCOMIDISTA_HTML = """<!DOCTYPE html>
<html>
<head><title>Crema fría de guisantes</title></head>
<body>
<article>
  <div data-dtm-region="articulo_cuerpo">
    <p>Una crema ideal para el verano.</p>
    <p><strong>Ingredientes</strong></p>
    <p>Para 4 personas</p>
    <ul>
      <li><span>800 g de guisantes</span></li>
      <li><span>1 cebolla picada</span></li>
    </ul>
    <p><strong>Preparación</strong></p>
    <p>1. Rehogar la cebolla en mantequilla.</p>
    <p>2. Añadir los guisantes, cocer y triturar.</p>
  </div>
</article>
</body>
</html>
"""

MICRODATA_HTML = """<!DOCTYPE html>
<html>
<head><meta property="og:title" content="Judías verdes con setas"></head>
<body>
  <ul>
    <li itemprop="recipeIngredient">400 g de judías verdes</li>
    <li itemprop="recipeIngredient">200 g de setas</li>
  </ul>
  <div itemprop="recipeInstructions">Cocer las judías y saltear con las setas.</div>
</body>
</html>
"""


class TestRecipe2Md(unittest.TestCase):
    def test_utils(self) -> None:
        self.assertEqual(
            recipe_to_md.slugify("¡Piña colada & niños!"),
            "pina-colada-ninos",
        )
        self.assertEqual(recipe_to_md.slugify("   "), "receta")
        self.assertEqual(
            recipe_to_md.clean_whitespace("Hola &amp; \xa0 mundo\n\n\n\nfin"),
            "Hola & mundo\n\nfin",
        )
        self.assertEqual(recipe_to_md.format_iso_duration("PT1H15M"), "1 h 15 min")
        self.assertEqual(recipe_to_md.format_iso_duration("P1DT2H"), "1 d 2 h")
        self.assertIsNone(recipe_to_md.format_iso_duration(None))
        self.assertEqual(recipe_to_md.yaml_escape('A "quote"\nline'), '"A \\"quote\\" line"')
        self.assertIn(
            "cocido-madrile%C3%B1o.jpg",
            recipe_to_md._encode_url_path("https://example.com/cocido-madrileño.jpg?w=1200"),
        )

    def test_candidate_urls(self) -> None:
        amp_url = (
            "https://www-recetasderechupete-com.cdn.ampproject.org/v/s/"
            "www.recetasderechupete.com/receta-de-lentejas/939/amp/"
            "?amp_js_v=a2#referrer=https%3A%2F%2Fwww.google.com&"
            "ampshare=https%3A%2F%2Fwww.recetasderechupete.com%2Freceta-de-lentejas%2F939%2F"
        )
        cands = recipe_to_md.candidate_urls(amp_url)
        self.assertIn("https://www.recetasderechupete.com/receta-de-lentejas/939/", cands)

        mobile_http = "http://www.mercadocalabajio.com/2016/10/bocadillo.html?m=1#frag"
        cands2 = recipe_to_md.candidate_urls(mobile_http)
        self.assertIn("http://www.mercadocalabajio.com/2016/10/bocadillo.html", cands2)
        self.assertTrue(any(c.startswith("https://") for c in cands2))

    def test_extract_modern_elcomidista(self) -> None:
        url = "https://elpais.com/gastronomia/recetas/2021/09/30/receta/1633022593_843329.html"
        rec = recipe_to_md.extract_recipe(url, MODERN_ELCOMIDISTA_HTML)
        self.assertEqual(rec["title"], "Curry verde tailandés")
        self.assertEqual(rec["author"], "Mikel López Iturriaga")
        self.assertEqual(rec["date"], "2021-10-07")
        self.assertEqual(rec["servings"], "2 raciones")
        self.assertEqual(rec["prep_time"], "15 min")
        self.assertEqual(rec["cook_time"], "20 min")
        self.assertEqual(rec["total_time"], "35 min")
        self.assertEqual(rec["hero_image"], "https://imagenes.elpais.com/preview.jpg")
        self.assertEqual(
            rec["inline_images"],
            [("https://imagenes.elpais.com/inline1.jpg", "Paso intermedio")],
        )
        self.assertEqual(
            rec["context_paragraphs"],
            [
                "Aunque la palabra curry se asocia a [la India](https://example.com/india), en *Tailandia* es maravilloso."
            ],
        )
        self.assertEqual(
            rec["ingredient_sections"],
            [
                ("Para la base", ["150 g de ternera", "50 g de leche de coco"]),
                ("Emplatado", ["Cilantro fresco"]),
            ],
        )
        self.assertEqual(
            rec["instructions"],
            [
                "Marcar la carne a fuego vivo.",
                "Añadir la leche de coco y servir.",
            ],
        )
        self.assertIn("el-comidista", rec["tags"])

    def test_extract_quirky_jsonld(self) -> None:
        rec = recipe_to_md.extract_recipe("https://example.com/sangria", QUIRKY_JSONLD_HTML)
        self.assertEqual(rec["title"], "Sangría casera")
        self.assertEqual(rec["hero_image"], "https://example.com/sangria.jpg")
        self.assertEqual(
            rec["ingredient_sections"],
            [(None, ["1 botella de vino tinto", "2 melocotones"])],
        )
        self.assertEqual(
            rec["instructions"],
            ["**Maceración**", "Cortar la fruta y mezclar con el vino."],
        )

    def test_extract_legacy_elcomidista_and_microdata(self) -> None:
        rec = recipe_to_md.extract_recipe(
            "https://elcomidista.elpais.com/2018/crema.html",
            LEGACY_ELCOMIDISTA_HTML,
        )
        self.assertEqual(rec["title"], "Crema fría de guisantes")
        self.assertEqual(rec["context_paragraphs"], ["Una crema ideal para el verano."])
        self.assertEqual(
            rec["ingredient_sections"],
            [("Para 4 personas", ["800 g de guisantes", "1 cebolla picada"])],
        )
        self.assertEqual(
            rec["instructions"],
            [
                "Rehogar la cebolla en mantequilla.",
                "Añadir los guisantes, cocer y triturar.",
            ],
        )

        rec_micro = recipe_to_md.extract_recipe("https://example.com/micro", MICRODATA_HTML)
        self.assertEqual(rec_micro["title"], "Judías verdes con setas")
        self.assertEqual(
            rec_micro["ingredient_sections"],
            [(None, ["400 g de judías verdes", "200 g de setas"])],
        )
        self.assertEqual(
            rec_micro["instructions"],
            ["Cocer las judías y saltear con las setas."],
        )

    def test_parse_plain_text_recipe(self) -> None:
        raw = (
            "Tostadas con tomate\n"
            "Desayuno mediterráneo.\n\n"
            "Ingredientes:\n"
            "- 2 rebanadas de pan\n"
            "- 1 tomate\n\n"
            "Preparación:\n"
            "1. Tostar el pan.\n"
            "2. Frotar el tomate.\n"
        )
        rec = recipe_to_md.parse_plain_text_recipe(raw, source_url="https://example.com/tostadas")
        self.assertEqual(rec["title"], "Tostadas con tomate")
        self.assertEqual(rec["context_paragraphs"], ["Desayuno mediterráneo."])
        self.assertEqual(
            rec["ingredient_sections"],
            [(None, ["2 rebanadas de pan", "1 tomate"])],
        )
        self.assertEqual(rec["instructions"], ["Tostar el pan.", "Frotar el tomate."])

    def test_render_markdown_and_storage(self) -> None:
        url = "https://elpais.com/gastronomia/recetas/2021/09/30/receta/1633022593_843329.html"
        rec = recipe_to_md.extract_recipe(url, MODERN_ELCOMIDISTA_HTML)
        md = recipe_to_md.render_markdown(
            rec,
            hero_img_ref="curry-verde-tailandes.jpg",
            inline_img_refs=[("curry-verde-tailandes-1.jpg", "Paso intermedio")],
            use_checkboxes=True,
        )
        self.assertIn('title: "Curry verde tailandés"', md)
        self.assertIn(f'source: "{url}"', md)
        self.assertIn("![Curry verde tailandés](curry-verde-tailandes.jpg)", md)
        self.assertIn("![Paso intermedio](curry-verde-tailandes-1.jpg)", md)
        self.assertIn("### Para la base\n\n- [ ] 150 g de ternera", md)
        self.assertIn("1. Marcar la carne a fuego vivo.", md)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            md_path = recipe_to_md.save_recipe(
                recipe=rec,
                out_dir=out_dir,
                images_subdir="",
                download_images=False,
                use_checkboxes=False,
                overwrite=False,
            )
            self.assertEqual(md_path.name, "curry-verde-tailandes.md")
            sources = recipe_to_md.index_existing_sources(out_dir)
            self.assertEqual(sources.get(url), md_path)


if __name__ == "__main__":
    unittest.main()
