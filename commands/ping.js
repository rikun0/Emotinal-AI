// commandsフォルダーの中に個別にコマンドを書いていくらしい
const { SlashCommandBuilder } = require('discord.js');

// module.exportsで他のファイルから呼び出せるようにする
module.exports = {
    data: new SlashCommandBuilder()
        .setName('ping') // コマンド名
        .setDescription('pong!'), // コマンドの説明
    async execute(interaction) {
        await interaction.reply('pong!'); // メッセージを返す
    }
}