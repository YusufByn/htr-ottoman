"""Tests de htr_ottoman.data.alto sur un ALTO minimal écrit à la main."""
from htr_ottoman.data.alto import read_alto

ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Description>
    <sourceImageInformation><fileName>1_2.jpg</fileName></sourceImageInformation>
  </Description>
  <Layout>
    <Page WIDTH="742" HEIGHT="1002.0" PHYSICAL_IMG_NR="1" ID="p1">
      <PrintSpace>
        <TextBlock ID="b1">
          <TextLine ID="l1" BASELINE="286 166 697 174">
            <Shape><Polygon POINTS="285 165 284 179 697 180 696 150"/></Shape>
            <String CONTENT="قنده كم على نماز"/>
          </TextLine>
          <TextLine ID="l2" BASELINE="285 223 699 230">
            <Shape><Polygon POINTS="284 222 284 238 699 240"/></Shape>
          </TextLine>
        </TextBlock>
      </PrintSpace>
    </Page>
  </Layout>
</alto>
"""


def test_page_attributes():
    page = read_alto(ALTO.encode("utf-8"))
    assert page.image_filename == "1_2.jpg"
    assert (page.width, page.height) == (742, 1002)
    assert len(page.lines) == 2


def test_line_with_text():
    line = read_alto(ALTO).lines[0]
    assert line.line_id == "l1" and line.block_id == "b1"
    assert line.text == "قنده كم على نماز"
    assert not line.is_empty
    assert line.baseline == [(286, 166), (697, 174)]
    assert line.polygon == [(285, 165), (284, 179), (697, 180), (696, 150)]


def test_line_without_string_is_empty():
    line = read_alto(ALTO).lines[1]
    assert line.text == ""
    assert line.is_empty
    assert len(line.polygon) == 3
