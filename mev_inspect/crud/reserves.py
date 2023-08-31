def get_reserves(db_session):
    result = db_session.execute("SELECT * FROM reserves")
    return result


def set_reserves(db_session, values):
    db_session.execute(
        """
        INSERT INTO reserves
        (pool_address, token0, token1)
        VALUES
        (:pool_address, :token0, :token1)
        """,
        params=values,
    )
    db_session.commit()


def get_synapse_reserves(db_session):
    result = db_session.execute("SELECT * FROM synapse_reserves")
    return result


def set_synapse_reserves(db_session, values):
    db_session.execute(
        """
        INSERT INTO synapse_reserves
        (pool_address_index, token)
        VALUES
        (:pool_address_index, :token)
        """,
        params=values,
    )
    db_session.commit()
