from ...crypto import Crypto
from ...network import Network


class Connect:
    async def connect(self):
        self.connection = Network(client=self)

        if self.auth and self.private_key is not None:
            try:
                self.guid = (await self.get_me()).user.user_guid
            except:
                print("Warning -> Failed to get_me")

        information = self.session.information()
        #self.logger.info(f'the session information was read {information}')

        if information:
            self.auth = information[1]
            self.guid = information[2]
            self.private_key = information[4]

            if isinstance(information[3], str):
                self.user_agent = information[3] or self.user_agent

        return self