/** Lists, rows of fields and button groups shared by the staff-services pages. */
export const OFFICE_STYLES = `
  .row,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: end;
  }

  .grow {
    flex: 1 1 200px;
  }

  .rows {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;

    li {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 8px;
    }
  }
`;
