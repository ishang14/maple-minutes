"""Regenerates tests/fixtures/*.xml (small hand-made Hansard samples). Run: python tests/make_fixtures.py"""

from pathlib import Path


def sitting(parl, sess, num, y, m, d, body):
    return f"""﻿<?xml version="1.0" encoding="UTF-8"?>
<Hansard xml:lang="EN" id="1">
  <ExtractedInformation>
    <ExtractedItem Name="MetaDateNumDay">{d}</ExtractedItem>
    <ExtractedItem Name="MetaDateNumMonth">{m}</ExtractedItem>
    <ExtractedItem Name="MetaDateNumYear">{y}</ExtractedItem>
    <ExtractedItem Name="MetaNumberNumber">{num:03d}</ExtractedItem>
    <ExtractedItem Name="SessionNumber">{sess}</ExtractedItem>
    <ExtractedItem Name="ParliamentNumber">{parl}</ExtractedItem>
  </ExtractedInformation>
  <HansardBody>
{body}
  </HansardBody>
</Hansard>
"""


B1 = """    <OrderOfBusiness id="10" Rubric="Other">
      <OrderOfBusinessTitle>Government Orders</OrderOfBusinessTitle>
      <SubjectOfBusiness id="11">
        <SubjectOfBusinessTitle>Cost of Living Relief Act, No. 2</SubjectOfBusinessTitle>
        <SubjectOfBusinessContent>
          <Intervention Type="Debate" ToC="Yes" ToCText="Mr. Ellis" id="100">
            <PersonSpeaking><Affiliation DbId="5" Type="2">Mr. Stephen Ellis (Cumberland—Colchester, CPC)</Affiliation>: </PersonSpeaking>
            <Content>
              <Timestamp Hr="14" Mn="05">(1405)</Timestamp>
              <FloorLanguage language="FR">[<I>Translation</I>]</FloorLanguage>
              <ParaText id="1">Mr. Speaker, I rise to speak to Bill <Document DbId="9" Type="3">C-31</Document> today.<?bk ?></ParaText>
              <ParaText id="2">It   matters   to my riding.</ParaText>
            </Content>
          </Intervention>
          <Intervention Type="Interjection" ToC="No" id="101">
            <PersonSpeaking><Affiliation DbId="7" Type="4">Hon. Jean-Yves Duclos</Affiliation>: </PersonSpeaking>
            <Content><ParaText id="3">Hear, hear!</ParaText></Content>
          </Intervention>
        </SubjectOfBusinessContent>
      </SubjectOfBusiness>
    </OrderOfBusiness>"""

B2 = """    <OrderOfBusiness id="20" Rubric="OralQuestionPeriod">
      <OrderOfBusinessTitle>Oral Questions</OrderOfBusinessTitle>
      <SubjectOfBusiness id="21">
        <SubjectOfBusinessTitle>Taxation</SubjectOfBusinessTitle>
        <SubjectOfBusinessContent>
          <Intervention Type="Question" ToC="Yes" id="200">
            <PersonSpeaking><Affiliation DbId="8" Type="9">Hon. Pierre Poilievre (Leader of the Opposition, CPC)</Affiliation>: </PersonSpeaking>
            <Content><ParaText id="4">Will the Prime Minister cancel the tax?</ParaText></Content>
          </Intervention>
          <Intervention Type="Debate" ToC="No" id="201">
            <PersonSpeaking><Affiliation DbId="9" Type="92">The Assistant Deputy Speaker (Mrs. Carol Hughes)</Affiliation></PersonSpeaking>
            <Content><ParaText id="5">The hon. member's time is up.</ParaText></Content>
          </Intervention>
          <Intervention Type="Debate" ToC="No" id="202">
            <PersonSpeaking><Affiliation DbId="10" Type="1">The Speaker</Affiliation></PersonSpeaking>
            <Content><ParaText id="6">Order.</ParaText></Content>
          </Intervention>
        </SubjectOfBusinessContent>
      </SubjectOfBusiness>
    </OrderOfBusiness>"""

B3 = """    <OrderOfBusiness id="30" Rubric="Other">
      <OrderOfBusinessTitle>Government Orders</OrderOfBusinessTitle>
      <SubjectOfBusiness id="31">
        <SubjectOfBusinessTitle>Cost of Living Relief Act, No. 2</SubjectOfBusinessTitle>
        <SubjectOfBusinessContent>
          <Intervention Type="Debate" ToC="Yes" id="300">
            <PersonSpeaking><Affiliation DbId="7" Type="2">Hon. Jean-Yves Duclos (Québec, Lib.)</Affiliation>: </PersonSpeaking>
            <Content><ParaText id="7">A speech with no bill reference.</ParaText></Content>
          </Intervention>
          <Intervention Type="Debate" ToC="No" id="301"><PersonSpeaking><Affiliation DbId="11" Type="2">Mr. Empty (X, NDP)</Affiliation>: </PersonSpeaking><Content/></Intervention>
        </SubjectOfBusinessContent>
      </SubjectOfBusiness>
    </OrderOfBusiness>"""

if __name__ == "__main__":
    out = Path(__file__).parent / "fixtures"
    out.mkdir(exist_ok=True)
    for name, args in {
        "sitting_a.xml": (44, 1, 1, 2022, 11, 2, B1),
        "sitting_b.xml": (44, 1, 2, 2022, 11, 3, B2),
        "sitting_c.xml": (45, 1, 3, 2025, 6, 10, B3),
    }.items():
        (out / name).write_text(sitting(*args), encoding="utf-8", newline="\n")
