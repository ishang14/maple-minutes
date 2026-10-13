export default function About() {
  return (
    <section
      aria-labelledby="about-title"
      className="rounded-xl border border-neutral-200 bg-white p-5 text-sm leading-relaxed dark:border-neutral-800 dark:bg-neutral-900"
    >
      <h2 id="about-title" className="text-base font-semibold">
        About and limitations
      </h2>
      <p className="mt-2">
        MapleMinutes searches the House of Commons Hansard, the official record of debates, from the 43rd
        Parliament (December 2019) onward. Answers are written by an AI model from the speeches it retrieves,
        and every claim links back to the exact speech.
      </p>
      <ul className="mt-3 list-disc space-y-1.5 pl-5">
        <li>
          <strong>AI can be wrong.</strong> It may paraphrase loosely, miss context, or misread irony. Open the
          numbered sources and check them before relying on or quoting anything. Quotation marks the app cannot
          match to the source are flagged under the answer.
        </li>
        <li>
          <strong>Speeches are positions, not facts.</strong> MPs argue for their party. The assistant reports what
          was said and by whom and is designed not to take sides.
        </li>
        <li>
          <strong>Limited coverage.</strong> English text only, House of Commons only (no Senate or committees),
          and only debates on law, justice and national security; foreign relations; and finance, economy and
          taxation. Topics are tagged automatically from headings and keywords, so some speeches are mislabelled
          or missing. Very short remarks are left out.
        </li>
        <li>
          <strong>Missing details.</strong> Ministers appear without a riding in the record, so some speakers have
          no riding or party shown.
        </li>
        <li>
          <strong>Trend chart.</strong> It counts speeches that contain most of your search words, so it measures
          mentions, not support or importance. Months differ in how many days the House sat, so try the share view.
        </li>
        <li>
          <strong>Slow first request.</strong> The free server sleeps when idle, so the first request can take 30
          to 60 seconds.
        </li>
      </ul>
      <p className="mt-3 text-xs text-neutral-600 dark:text-neutral-400">
        Source: House of Commons Hansard. Reproduced accurately and for non-commercial use under the House of
        Commons reproduction permission. This is not an official publication of the House of Commons.
      </p>
    </section>
  )
}
