// 必要なモジュールのインポート
const fs = require('fs');
const { REST, Routes } = require('discord.js');
require('dotenv').config();

// コマンドファイルの読み込み
const commands = []; // コマンドを格納する配列
const commandFiles = fs.readdirSync('./commands').filter(file => file.endsWith('.js'));

// コマンドを配列に追加
for (const file of commandFiles) {
    const command = require(`./commands/${file}`);
    commands.push(command.data.toJSON());  // JSONデータに変換して配列に追加
}

// Discord APIとの通信の準備
const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

// コマンドをデプロイ
(async () => {
    try {
        console.log('デプロイを開始します。');
        await rest.put(
            Routes.applicationGuildCommands(process.env.APPLICATION_ID, process.env.GUILD_ID),
            { body: commands }
        );
        console.log('デプロイが完了しました。');
    } catch (error) {
        console.error(error);
    }
})();
