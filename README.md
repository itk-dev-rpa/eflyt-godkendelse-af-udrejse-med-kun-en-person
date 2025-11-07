# Eflyt Godkendelse af Udrejse med kun en person

This RPA finds cases in eFlyt, where only one person is moving to a different country and confirms these, sending a letter to the citizen.

## Running process

This process is designed to run in [OpenOrchestrator](https://github.com/itk-dev-rpa/OpenOrchestrator).
A credential named "Eflyt" is required for login to eFlyt, and a credential called "Event Log" with a connection string to an eventlog database is required for eventlogging.