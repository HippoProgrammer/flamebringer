psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    \c flamebringer

    CREATE TYPE PROPOSALTYPE AS ENUM ('legislative', 'constitutional', 'honorary', 'holiday', 'treaty');
    CREATE TYPE PROPOSALSTATE AS ENUM ('draft', 'debate', 'vote', 'passed', 'failed', 'repealed');

    CREATE TABLE IF NOT EXISTS Halls (
    Ref SERIAL PRIMARY KEY,
    Name TEXT NOT NULL,
    Authors BIGINT ARRAY NOT NULL,
    Thread BIGINT NOT NULL CHECK UNIQUE,
    Type PROPOSALTYPE NOT NULL,
    State PROPOSALSTATE NOT NULL,
    ID TEXT CHECK UNIQUE,
    Results INT ARRAY
    );
EOSQL