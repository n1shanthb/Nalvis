import { useSearchParams } from "react-router-dom";
import { Btn, ErrorState, Loading, PageHead, Panel } from "../components/ui";
import { QueryBoundary, useApiQuery } from "../lib/query";
import type { JsonObject } from "../lib/api";

export default function CalendarPage() {
  const [params, setParams] = useSearchParams();
  const today = new Date();
  const year = Number(params.get("year") || today.getFullYear());
  const month = Number(params.get("month") || today.getMonth() + 1);
  const calendarId = params.get("calendar_id") || "primary";
  const calendar = useApiQuery(["calendar", year, month, calendarId], `/calendar?year=${year}&month=${month}&calendar_id=${encodeURIComponent(calendarId)}`);
  const navigate = (target: JsonObject) => setParams({ year: String(target.year), month: String(target.month), calendar_id: calendarId });

  if (calendar.isPending) return <Loading />;
  if (calendar.error) return <ErrorState error={calendar.error} />;
  const data = calendar.data;

  return (
    <>
      <PageHead
        title={data.month_label}
        subtitle={data.configured ? "Month view from your connected Google Calendar." : "Google OAuth is not configured."}
      />
      {!data.configured ? (
        <div className="banner-warn">
          <strong>Calendar not connected</strong>
          <p className="muted">Configure Gmail/Google OAuth credentials to load events.</p>
        </div>
      ) : (
        <>
          <div className="toolbar">
            <Btn className="ghost" onClick={() => navigate(data.previous!)}>← Previous</Btn>
            <Btn className="ghost" onClick={() => navigate(data.next!)}>Next →</Btn>
            {data.calendars.length > 0 && (
              <select
                className="tool-filter"
                value={calendarId}
                onChange={e => setParams({ year: String(year), month: String(month), calendar_id: e.target.value })}
              >
                {data.calendars.map((cal: JsonObject) => (
                  <option key={cal.id} value={cal.id}>{cal.summary || cal.id}</option>
                ))}
              </select>
            )}
          </div>
          <Panel title="Schedule">
            <div className="calendar">
              <div className="weekdays">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => <span key={d}>{d}</span>)}</div>
              {data.matrix.map((week: string[], i: number) => (
                <div className="week" key={i}>
                  {week.map(day => (
                    <div className="day" key={day}>
                      <b>{day.slice(-2)}</b>
                      {(data.by_day?.[day] || []).slice(0, 3).map((event: JsonObject) => (
                        <a key={event.id} href={event.html_link || undefined} target="_blank" rel="noreferrer" className="cal-event">
                          {event.summary || "(no title)"}
                        </a>
                      ))}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
